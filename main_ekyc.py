# ==========================================
# FILE: main_ekyc.py
# Mô tả: Hệ thống EKYC kết hợp khuôn mặt + giọng nói
# ==========================================
from database import EKYCDatabase
from face_recognition_module import FaceRecognition
from voice_verification_module import VoiceVerification
import time


class EKYCSystem:
    def __init__(self):
        self.db = EKYCDatabase()
        self.face_rec = FaceRecognition()
        self.voice_ver = VoiceVerification()

    # ===========================================================
    # 1️⃣ Đăng ký người dùng mới
    # ===========================================================
    def register_user(self):
        print("\n" + "="*50)
        print("=== ĐĂNG KÝ NGƯỜI DÙNG MỚI ===")
        print("="*50)

        username = input("Tên đăng nhập: ")
        password = input("Mật khẩu: ")
        email = input("Email: ")

        # Thêm user vào database
        user_id = self.db.add_user(username, password, email)
        print(f"✅ Đã tạo user với ID: {user_id}")

        # ===========================================================
        # PHASE 1: Đăng ký khuôn mặt (5 góc)
        # ===========================================================
        print("\n" + "="*50)
        print("=== PHASE 1: ĐĂNG KÝ KHUÔN MẶT (5 GÓC) ===")
        print("="*50)
        self.face_rec.capture_five_angles(user_id)

        # ===========================================================
        # PHASE 2: Đăng ký OTP và 6 ảnh khuôn mặt khi đọc
        # ===========================================================
        print("\n" + "="*50)
        print("=== PHASE 2: ĐĂNG KÝ OTP VÀ 6 ẢNH KHUÔN MẶT ===")
        print("="*50)
        print("💡 Sẽ có mã OTP 6 số hiện lên, hãy đọc to và rõ TỪNG SỐ")
        print("📷 Hệ thống sẽ chụp 6 ảnh khuôn mặt và lưu vào Database")
        print("🎯 Mỗi khi bạn mở miệng đọc một số, hệ thống sẽ chụp 1 ảnh")
        
        input("Nhấn Enter khi sẵn sàng...")
        
        success, image_count = self.face_rec.capture_face_for_each_otp_digit(user_id)
        if not success or image_count < 6:
            print(f"⚠️ Chỉ chụp được {image_count}/6 ảnh")
            retry = input("❌ Bạn có muốn thử lại Phase 2? (y/n): ").strip().lower()
            if retry == 'y':
                success, image_count = self.face_rec.capture_face_for_each_otp_digit(user_id)
        else:
            print(f"✅ Đã chụp thành công {image_count}/6 ảnh khuôn mặt khi đọc OTP")

        # ===========================================================
        # PHASE 3: Đăng ký sinh trắc học giọng nói
        # ===========================================================
        print("\n" + "="*50)
        print("=== PHASE 3: ĐĂNG KÝ GIỌNG NÓI ===")
        print("="*50)
        print("💡 Lưu ý: Nói tự nhiên, nội dung bên trên")
        voice_success = self.voice_ver.enroll_voice(user_id)

        print("\n🎉 HOÀN TẤT ĐĂNG KÝ 3 PHASE")
        print(f"👤 Người dùng: {username}")
        print("📊 Dữ liệu đã lưu:")
        print(f"   - 5 góc khuôn mặt (Phase 1)")
        print(f"   - OTP và {image_count} ảnh khuôn mặt khi đọc (Phase 2)") 
        print(f"   - 3 mẫu giọng nói sinh trắc (Phase 3)")

    # Cập nhật phương thức verify_user - Sử dụng Phase 2 xác thực mới
    def verify_user(self):
        print("\n" + "="*50)
        print("=== XÁC THỰC EKYC ===")
        print("="*50)

        username = input("Tên đăng nhập: ")

        # Lấy user_id
        with self.db.conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            result = cur.fetchone()
            if not result:
                print("❌ Không tìm thấy người dùng.")
                return False
            user_id = result[0]

        print(f"\n🔍 Đang xác thực cho: {username}")
        print("🎯 Ngưỡng xác thực: 70%")

        # -----------------------------
        # XÁC THỰC KHUÔN MẶT VỚI LIVENESS
        # -----------------------------
        print("\n" + "="*30)
        print("📷 XÁC THỰC KHUÔN MẶT + LIVENESS")
        print("="*30)
        time.sleep(1)

        face_verified, face_confidence, face_liveness = self.face_rec.verify_face(user_id)
        if not face_verified:
            print("❌ Xác thực khuôn mặt thất bại.")
            self.db.log_kyc_session(user_id, False, face_confidence, 0.0)
            return False
        print(f"✅ Xác thực khuôn mặt thành công")
        print(f"   - Độ khớp: {face_confidence:.1%}")
        print(f"   - Liveness: {face_liveness:.1%}")

        # ===========================================================
        # PHASE 2: Xác thực OTP đã lưu và kiểm tra deepfake
        # ===========================================================
        print("\n" + "="*50)
        print("=== PHASE 2: XÁC THỰC OTP ĐÃ LƯU VÀ KIỂM TRA DEEPFAKE ===")
        print("="*50)
        print("🔐 Sử dụng OTP đã lưu trong hệ thống")
        print("🗣️ Hãy đọc to và rõ từng chữ số OTP")
        print("📷 Hệ thống sẽ chụp 6 ảnh và kiểm tra:")
        print("   • So sánh với khuôn mặt đã đăng ký")
        print("   • Phát hiện deepfake (nét mất khúc, artifacts)")
        
        input("Nhấn Enter khi sẵn sàng...")
        
        # Kiểm tra xem user đã có OTP trong database chưa
        otp_count = self.db.get_otp_face_count(user_id)
        if otp_count == 0:
            print("❌ Người dùng chưa đăng ký OTP. Vui lòng đăng ký trước.")
            return False
        
        # Xác thực với OTP đã lưu
        otp_verified, otp_face_confidence, deepfake_score = self.face_rec.verify_face_with_saved_otp(user_id)
        
        if not otp_verified:
            print("❌ Xác thực OTP và kiểm tra deepfake thất bại.")
            self.db.log_kyc_session(user_id, False, face_confidence, 0.0)
            return False
        
        print(f"✅ Xác thực OTP và kiểm tra deepfake thành công")
        print(f"   - Độ khớp khuôn mặt: {otp_face_confidence:.1%}")
        print(f"   - Deepfake score: {deepfake_score:.1%}")

        # -----------------------------
        # XÁC THỰC GIỌNG NÓI VỚI LIVENESS
        # -----------------------------
        print("\n" + "="*30)
        print("🎤 XÁC THỰC GIỌNG NÓI + LIVENESS")
        print("="*30)
        voice_verified, voice_confidence, voice_liveness = self.voice_ver.verify_voice(user_id)
        if not voice_verified:
            print("❌ Xác thực giọng nói thất bại.")
            self.db.log_kyc_session(user_id, False, face_confidence, voice_confidence)
            return False
        print(f"✅ Xác thực giọng nói thành công")
        print(f"   - Độ khớp: {voice_confidence:.1%}")
        print(f"   - Liveness: {voice_liveness:.1%}")

        # -----------------------------
        # KẾT QUẢ TỔNG HỢP
        # -----------------------------
        overall_verified = face_verified and otp_verified and voice_verified
        overall_conf = (face_confidence + otp_face_confidence + voice_confidence) / 3
        
        self.db.log_kyc_session(user_id, overall_verified, face_confidence, voice_confidence)

        print("\n" + "="*50)
        if overall_verified:
            print(f"🎉 XÁC THỰC EKYC THÀNH CÔNG ({overall_conf:.1%})")
            print("📊 Chi tiết:")
            print(f"   • Khuôn mặt: {face_confidence:.1%}")
            print(f"   • OTP + Deepfake check: {otp_face_confidence:.1%}")
            print(f"   • Giọng nói: {voice_confidence:.1%}")
        else:
            print(f"⚠️ XÁC THỰC EKYC THẤT BẠI ({overall_conf:.1%})")
        print("="*50)

        return overall_verified
    # ===========================================================
    # 3️⃣ Xác thực nhanh (chỉ khuôn mặt)
    # ===========================================================
    def quick_verify(self):
        print("\n⚡ XÁC THỰC NHANH")
        username = input("Tên đăng nhập: ")

        with self.db.conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            result = cur.fetchone()
            if not result:
                print("❌ Không tìm thấy người dùng.")
                return False
            user_id = result[0]

        print(f"🔍 Đang xác thực khuôn mặt cho {username} ...")
        verified, score, liveness = self.face_rec.verify_face(user_id)

        if verified:
            print(f"✅ Thành công")
            print(f"   - Độ khớp: {score:.1%}")
            print(f"   - Liveness: {liveness:.1%}")
        else:
            print(f"❌ Thất bại")
            print(f"   - Độ khớp: {score:.1%}")
            print(f"   - Liveness: {liveness:.1%}")

        return verified

    # ===========================================================
    # 4️⃣ Xác thực bằng OTP (chỉ giọng nói)
    # ===========================================================
    def verify_by_otp(self):
        print("\n" + "="*50)
        print("=== NHẬN DIỆN BẰNG MÃ OTP ===")
        print("="*50)

        username = input("Tên đăng nhập: ")

        # Lấy user_id
        with self.db.conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            result = cur.fetchone()
            if not result:
                print("❌ Không tìm thấy người dùng.")
                return False
            user_id = result[0]

        print(f"\n🔍 Đang xác thực giọng nói cho: {username}")
        print("🎯 Phương thức: Đọc mã OTP")

        # -----------------------------
        # XÁC THỰC GIỌNG NÓI VỚI OTP
        # -----------------------------
        voice_verified, voice_confidence, voice_liveness = self.voice_ver.verify_voice(user_id)
        
        if voice_verified:
            print("\n" + "="*50)
            print(f"🎉 XÁC THỰC OTP THÀNH CÔNG")
            print(f"📊 Độ khớp: {voice_confidence:.1%}")
            print(f"📊 Liveness: {voice_liveness:.1%}")
            print("="*50)
        else:
            print("\n" + "="*50)
            print(f"❌ XÁC THỰC OTP THẤT BẠI")
            print(f"📊 Độ khớp: {voice_confidence:.1%}")
            print(f"📊 Liveness: {voice_liveness:.1%}")
            print("="*50)

        return voice_verified

# ===========================================================
# CHƯƠNG TRÌNH CHÍNH
# ===========================================================
def main():
    system = EKYCSystem()

    while True:
        print("\n" + "🔐"*25)
        print("🔐        HỆ THỐNG EKYC KHUÔN MẶT + GIỌNG NÓI        🔐")
        print("🔐"*25)
        print("\n📋 MENU CHÍNH:")
        print(" 1. 📝 Đăng ký người dùng mới")
        print(" 2. 🔍 Xác thực EKYC (Face + Voice)")
        print(" 3. ⚡ Xác thực nhanh (khuôn mặt)")
        print(" 4. 🔐 Nhận diện bằng OTP (giọng nói)")
        print(" 5. 🚪 Thoát")

        choice = input("\n👉 Chọn (1-5): ").strip()

        if choice == '1':
            system.register_user()
        elif choice == '2':
            system.verify_user()
        elif choice == '3':
            system.quick_verify()
        elif choice == '4':
            system.verify_by_otp()
        elif choice == '5':
            print("\n👋 Cảm ơn bạn đã sử dụng hệ thống EKYC!")
            break
        else:
            print("❌ Lựa chọn không hợp lệ.")

        input("\n⏎ Nhấn Enter để tiếp tục...")

if __name__ == "__main__":
    try:
        main()
    finally:
        import gc
        gc.collect()
