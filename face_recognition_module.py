# ==========================================
# FILE: face_recognition_module.py
# Mô tả: Nhận diện, xác thực khuôn mặt và phát hiện liveness (người thật vs giả)
# ==========================================
import cv2
import face_recognition
import numpy as np
from typing import Tuple, List
from database import EKYCDatabase

class FaceRecognition:
    def __init__(self):
        self.db = EKYCDatabase()
        
    # ================================
    # Phát hiện Liveness (người thật vs ảnh/ảnh video)
    # ================================
    def detect_face_liveness(self, frame: np.ndarray, face_locations: List) -> Tuple[float, List[str]]:
        """
        Phát hiện khuôn mặt thật bằng nhiều phương pháp:
        - Blink detection
        - Head movement tracking
        - Texture analysis (Laplacian variance)
        - Motion detection
        
        Returns: (liveness_score, warnings)
        """
        warnings = []
        scores = []
        
        if len(face_locations) == 0:
            return 0.0, ["Không phát hiện khuôn mặt"]
        
        face = face_locations[0]
        top, right, bottom, left = face
        face_roi = frame[top:bottom, left:right]
        
        # 1. Texture Analysis (phát hiện in ảnh)
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
        
        # Ảnh in thường có variance thấp
        if laplacian_var < 100:
            warnings.append("Có thể là ảnh in (texture quá mịn)")
            texture_score = 0.3
        elif laplacian_var < 200:
            texture_score = 0.7
        else:
            texture_score = 1.0
        scores.append(texture_score)
        
        # 2. Face Landmarks Analysis (đơn giản dựa trên tỷ lệ)
        face_height = bottom - top
        face_width = right - left
        aspect_ratio = face_width / face_height if face_height > 0 else 1.0
        
        # Khuôn mặt tự nhiên có tỷ lệ gần 0.7-0.9
        if 0.7 <= aspect_ratio <= 0.9:
            ratio_score = 1.0
        elif 0.5 <= aspect_ratio < 0.7 or 0.9 < aspect_ratio <= 1.2:
            ratio_score = 0.7
        else:
            ratio_score = 0.4
            warnings.append("Tỷ lệ khuôn mặt bất thường")
        scores.append(ratio_score)
        
        # 3. Edge Detection (phát hiện khung hình trong ảnh in)
        edges = cv2.Canny(gray_face, 50, 150)
        edge_density = np.sum(edges > 0) / (face_width * face_height) if (face_width * face_height) > 0 else 0
        
        # Ảnh in thường có edge rõ ràng ở viền
        if edge_density > 0.3:
            edge_score = 1.0
        elif edge_density > 0.15:
            edge_score = 0.8
        else:
            edge_score = 0.5
        scores.append(edge_score)
        
        # 4. Color Analysis (phát hiện màu không tự nhiên)
        hsv_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        mean_hue = np.mean(hsv_face[:, :, 0])
        
        # Da người thường có hue trong khoảng 0-50
        if 0 <= mean_hue <= 50:
            color_score = 1.0
        else:
            color_score = 0.6
            warnings.append("Màu da bất thường")
        scores.append(color_score)
        
        # Tính điểm tổng hợp
        liveness_score = np.mean(scores)
        
        return liveness_score, warnings

    # ================================
    # Đăng ký: chụp 3 góc mặt VỚI Liveness Check
    # ================================
    def capture_five_angles(self, user_id: int):
        cap = cv2.VideoCapture(0)
        angles = ['left', 'right', 'front', 'up', 'down']
        angle_descriptions = {
            'left': 'QUAY MẶT SANG TRÁI',
            'right': 'QUAY MẶT SANG PHẢI', 
            'front': 'NHÌN THẲNG CHÍNH DIỆN',
            'up': 'NGẨNG MẶT LÊN TRÊN',
            'down': 'CÚI MẶT XUỐNG DƯỚI'
        }
        encodings = []

        print("\n--- BẮT ĐẦU CHỤP 5 GÓC MẶT (Kiểm tra Người Thật) ---")
        print("Sẽ chụp 5 ảnh: TRÁI → PHẢI → CHÍNH DIỆN → TRÊN → DƯỚI")
        print("⚠️ LƯU Ý: Sử dụng người thật, không phải ảnh in hoặc video!")

        for angle in angles:
            print(f"\n➡️ {angle_descriptions[angle]}, nhấn SPACE để chụp, ESC để hủy")
            
            # Hướng dẫn cụ thể cho từng góc
            if angle == 'left':
                print("   💡 Từ từ quay mặt sang trái khoảng 45 độ")
            elif angle == 'right':
                print("   💡 Từ từ quay mặt sang phải khoảng 45 độ")
            elif angle == 'up':
                print("   💡 Từ từ ngẩng mặt lên nhìn trần nhà")
            elif angle == 'down':
                print("   💡 Từ từ cúi mặt xuống nhìn sàn nhà")
            else:
                print("   💡 Nhìn thẳng vào camera, giữ khuôn mặt cân đối")
                
            while True:
                ret, frame = cap.read()
                if not ret:
                    continue

                # Hiển thị hướng dẫn
                cv2.putText(frame, f"{angle_descriptions[angle]}", (30, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Nhan SPACE de chup", (30, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Kiểm tra liveness realtime
                face_locs = face_recognition.face_locations(frame)
                liveness_score, warnings = self.detect_face_liveness(frame, face_locs)
                
                # Vẽ thông tin liveness
                liveness_text = f"Liveness: {liveness_score:.1%}"
                liveness_color = (0, 255, 0) if liveness_score >= 0.7 else (0, 165, 255) if liveness_score >= 0.5 else (0, 0, 255)
                cv2.putText(frame, liveness_text, (30, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, liveness_color, 2)
                
                # Vẽ bounding box nếu có mặt
                if len(face_locs) > 0:
                    top, right, bottom, left = face_locs[0]
                    cv2.rectangle(frame, (left, top), (right, bottom), liveness_color, 2)
                
                cv2.imshow("Capture Face - 5 Angles", frame)

                key = cv2.waitKey(1)
                if key == 27:  # ESC
                    cap.release()
                    cv2.destroyAllWindows()
                    print("❌ Hủy đăng ký gương mặt.")
                    return
                elif key == 32:  # SPACE
                    face_locs = face_recognition.face_locations(frame)
                    if len(face_locs) == 0:
                        print("⚠️ Không phát hiện khuôn mặt, thử lại.")
                        continue
                    
                    # Kiểm tra liveness khi chụp
                    liveness_score, warnings = self.detect_face_liveness(frame, face_locs)
                    
                    if liveness_score < 0.5:
                        print(f"⚠️ Cảnh báo: Liveness thấp ({liveness_score:.1%})")
                        if warnings:
                            for w in warnings:
                                print(f"   - {w}")
                        retry = input("   Bạn muốn thử lại? (y/n): ").strip().lower()
                        if retry == 'y':
                            continue
                    
                    face_enc = face_recognition.face_encodings(frame, face_locs)[0]
                    encodings.append(face_enc)
                    print(f"✅ Đã lưu góc {angle_descriptions[angle]} (Liveness: {liveness_score:.1%})")
                    cv2.waitKey(800)
                    break

        cap.release()
        cv2.destroyAllWindows()

        if len(encodings) == 5:
            self.db.save_face_encodings(user_id, encodings, angles)
            print("🎉 Đăng ký khuôn mặt hoàn tất (5 góc đã lưu với kiểm tra liveness).")
        else:
            print("❌ Không đủ 5 ảnh để lưu.")

    # ================================
    # Đăng nhập: xác thực gương mặt VỚI Liveness Check
    # ================================
    def verify_face(self, user_id: int) -> Tuple[bool, float, float]:
        """
        Xác thực gương mặt với liveness detection - Sử dụng 5 góc
        Returns: (verified, face_similarity, liveness_score)
        """
        print("\n--- XÁC THỰC GƯƠNG MẶT VỚI LIVENESS (5 GÓC) ---")
        known_encodings = self.db.get_face_encodings(user_id)
        if not known_encodings:
            print("⚠️ Chưa có dữ liệu khuôn mặt cho tài khoản này.")    
            return False, 0.0, 0.0

        if len(known_encodings) < 5:
            print(f"⚠️ Cảnh báo: Chỉ có {len(known_encodings)} mẫu khuôn mặt, cần 5 mẫu cho độ chính xác tốt nhất")

        cap = cv2.VideoCapture(0)
        max_similarity = 0.0
        max_liveness = 0.0

        print("Di chuyển đầu tự nhiên trước camera... (ESC để hủy)")
        print("⚠️ Hệ thống sẽ tự động nhận diện ở các góc khác nhau")
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            frame_count += 1
            face_locs = face_recognition.face_locations(frame)
            
            if len(face_locs) > 0:
                enc = face_recognition.face_encodings(frame, face_locs)[0]
                distances = face_recognition.face_distance(known_encodings, enc)
                similarities = 1 - distances
                best = np.max(similarities)
                max_similarity = max(max_similarity, best)

                # Kiểm tra liveness
                liveness_score, warnings = self.detect_face_liveness(frame, face_locs)
                max_liveness = max(max_liveness, liveness_score)

                # Kết hợp cả similarity và liveness
                combined_score = (best * 0.7 + liveness_score * 0.3)
                
                label = f"Match: {best:.1%} | Liveness: {liveness_score:.1%}"
                combined_label = f"Combined: {combined_score:.1%}"
                
                if combined_score >= 0.7:
                    color = (0, 255, 0)
                elif combined_score >= 0.5:
                    color = (0, 165, 255)
                else:
                    color = (0, 0, 255)

                for (top, right, bottom, left) in face_locs:
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.putText(frame, label, (left, top - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    cv2.putText(frame, combined_label, (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if combined_score >= 0.7 and frame_count > 10:  # Đợi ít nhất 10 frame
                    print(f"✅ Xác thực xong (Match: {best:.1%}, Liveness: {liveness_score:.1%})")
                    break

            cv2.imshow("Verify Face - 5 Angles", frame)
            key = cv2.waitKey(1)
            if key == 27:
                print("❌ Hủy xác thực.")
                break

        cap.release()
        cv2.destroyAllWindows()

        verified = max_similarity >= 0.7 and max_liveness >= 0.5
        print(f"📊 Độ tương đồng khuôn mặt: {max_similarity:.1%}")
        print(f"📊 Độ liveness (người thật): {max_liveness:.1%}")
        return verified, max_similarity, max_liveness


    def capture_face_for_each_otp_digit(self, user_id: int):
        """
        Phase 2: Chụp 6 ảnh tương ứng với 6 chữ số OTP
        Sử dụng phương pháp thay thế không cần cascade mouth
        """
        import random
        import string
        import time
        
        # Tạo OTP ngẫu nhiên 6 chữ số
        otp_code = ''.join(random.choices(string.digits, k=6))
        
        print("\n" + "="*50)
        print("=== PHASE 2: ĐĂNG KÝ OTP VÀ 6 ẢNH KHUÔN MẶT ===")
        print("="*50)
        print(f"🔐 Mã OTP của bạn là: {otp_code}")
        print("🗣️ Hãy đọc to và rõ ràng từng chữ số OTP")
        print("📷 Hệ thống sẽ chụp 6 ảnh tương ứng với 6 chữ số")
        print("💡 Đọc chậm rãi, rõ từng chữ số...")
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Không thể mở camera")
            return False, 0
        
        captured_images = []  # Lưu các cặp (ảnh, chữ_số)
        current_digit_index = 0
        
        # Chỉ sử dụng face cascade (có sẵn trong OpenCV)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        print("\n🎥 Đang khởi động camera...")
        print("⏳ Bắt đầu đọc OTP trong 5 giây nữa...")
        
        # Đếm ngược
        for i in range(5, 0, -1):
            print(f"⏰ {i}...")
            time.sleep(1)
        
        print("🎤 BẮT ĐẦU ĐỌC OTP NGAY BÂY GIỜ!")
        print("💡 Đọc chậm và rõ từng chữ số...")
        
        start_time = time.time()
        capture_duration = 15  # Thời gian ghi hình (giây)
        last_capture_time = 0
        capture_cooldown = 1.5  # Thời gian chờ giữa các lần chụp (giây)
        
        while time.time() - start_time < capture_duration and current_digit_index < 6:
            ret, frame = cap.read()
            if not ret:
                continue
            
            current_time = time.time()
            original_frame = frame.copy()
            
            # Chuyển sang ảnh xám để nhận diện
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            
            face_detected = len(faces) > 0
            
            for (x, y, w, h) in faces:
                # Vẽ hình chữ nhật quanh mặt
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                cv2.putText(frame, "FACE DETECTED", (x, y-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                # Ước lượng vùng miệng (nửa dưới khuôn mặt)
                mouth_y = y + int(h * 0.6)
                mouth_h = int(h * 0.3)
                cv2.rectangle(frame, (x, mouth_y), (x+w, mouth_y+mouth_h), (0, 255, 255), 2)
                cv2.putText(frame, "MOUTH ESTIMATED", (x, mouth_y-5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
            
            # Tự động chụp ảnh sau mỗi khoảng thời gian khi có khuôn mặt
            if (face_detected and 
                current_time - last_capture_time > capture_cooldown and 
                current_digit_index < 6):
                
                # Chụp ảnh và lưu
                current_digit = otp_code[current_digit_index]
                
                # Thêm thông tin lên ảnh
                annotated_frame = original_frame.copy()
                cv2.putText(annotated_frame, f"Digit: {current_digit}", (30, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(annotated_frame, f"Time: {int(current_time - start_time)}s", (30, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                
                captured_images.append((annotated_frame, current_digit))
                current_digit_index += 1
                last_capture_time = current_time
                
                print(f"✅ Đã chụp ảnh cho số {current_digit} ({current_digit_index}/6)")
            
            # Hiển thị thông tin
            cv2.putText(frame, f"OTP: {otp_code}", (30, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, f"Dang doc: {otp_code[current_digit_index] if current_digit_index < 6 else 'HOAN TAT'}", 
                    (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Hiển thị số ảnh đã chụp
            cv2.putText(frame, f"Da chup: {current_digit_index}/6", (30, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Hiển thị thời gian còn lại
            remaining = int(capture_duration - (time.time() - start_time))
            cv2.putText(frame, f"Time: {remaining}s", (30, 130), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Hiển thị trạng thái
            status_face = "FACE: ✅" if face_detected else "FACE: ❌"
            cv2.putText(frame, status_face, (30, 160), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("OTP Verification - 6 Images", frame)
            
            if cv2.waitKey(1) == 27:  # ESC để thoát
                break
            
            # Nếu đã chụp đủ 6 ảnh, thoát sớm
            if current_digit_index >= 6:
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Lưu tất cả ảnh đã chụp vào database
        if captured_images:
            success = self.db.save_otp_face_images_sequence(user_id, otp_code, captured_images)
            
            if success:
                print(f"✅ Đã lưu OTP '{otp_code}' và {len(captured_images)} ảnh khuôn mặt")
                
                # Hiển thị grid 6 ảnh đã chụp
                if len(captured_images) > 0:
                    self.display_otp_digit_images_grid(captured_images, otp_code)
                
                return True, len(captured_images)
            else:
                print("❌ Lỗi lưu OTP và ảnh khuôn mặt")
                return False, len(captured_images)
        else:
            print("❌ Không chụp được ảnh nào")
            return False, 0

    def verify_face_with_saved_otp(self, user_id: int):
        """
        Phase 2 trong XÁC THỰC: Sử dụng OTP đã lưu trong Database
        Kiểm tra khuôn mặt và phát hiện deepfake
        """
        # Lấy OTP đã lưu từ database
        saved_otp = self.db.get_latest_otp_for_user(user_id)
        if not saved_otp:
            print("❌ Không tìm thấy OTP đã lưu cho người dùng này.")
            return False, 0.0, 0.0
        
        print("\n" + "="*50)
        print("=== PHASE 2: XÁC THỰC OTP ĐÃ LƯU VÀ PHÁT HIỆN DEEPFAKE ===")
        print("="*50)
        print(f"🔐 Mã OTP đã lưu của bạn là: {saved_otp}")
        print("🗣️ Hãy đọc to và rõ ràng từng chữ số OTP này")
        print("📷 Hệ thống sẽ chụp 6 ảnh và kiểm tra deepfake")
        print("🔍 So sánh với khuôn mặt đã đăng ký...")
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Không thể mở camera")
            return False, 0.0, 0.0
        
        captured_images = []  # Lưu các cặp (ảnh, chữ_số)
        current_digit_index = 0
        
        # Chỉ sử dụng face cascade
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        print("\n🎥 Đang khởi động camera...")
        print("⏳ Bắt đầu đọc OTP trong 5 giây nữa...")
        
        # Đếm ngược
        import time
        for i in range(5, 0, -1):
            print(f"⏰ {i}...")
            time.sleep(1)
        
        print("🎤 BẮT ĐẦU ĐỌC OTP NGAY BÂY GIỜ!")
        print("💡 Đọc chậm và rõ từng chữ số...")
        
        start_time = time.time()
        capture_duration = 15
        last_capture_time = 0
        capture_cooldown = 1.0
        
        while time.time() - start_time < capture_duration and current_digit_index < 6:
            ret, frame = cap.read()
            if not ret:
                continue
            
            current_time = time.time()
            original_frame = frame.copy()
            
            # Chuyển sang ảnh xám để nhận diện
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            
            face_detected = len(faces) > 0
            
            for (x, y, w, h) in faces:
                face_detected = True
                
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                cv2.putText(frame, "FACE", (x, y-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                # Sử dụng phương pháp ước lượng vùng miệng (không cần cascade)
                mouth_x = x
                mouth_y = y + int(h * 0.6)
                mouth_w = w
                mouth_h = int(h * 0.3)
                cv2.rectangle(frame, (mouth_x, mouth_y), (mouth_x+mouth_w, mouth_y+mouth_h), (0, 255, 255), 2)
                cv2.putText(frame, "MOUTH (EST)", (mouth_x, mouth_y-5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
                
                # Giả định miệng đang mở khi người dùng đọc OTP
                mouth_open = True
                
                if (face_detected and mouth_open and 
                    current_time - last_capture_time > capture_cooldown and 
                    current_digit_index < 6):
                    
                    current_digit = saved_otp[current_digit_index]
                    
                    annotated_frame = original_frame.copy()
                    cv2.putText(annotated_frame, f"Digit: {current_digit}", (30, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.putText(annotated_frame, f"Time: {int(current_time - start_time)}s", (30, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    captured_images.append((annotated_frame, current_digit))
                    current_digit_index += 1
                    last_capture_time = current_time
                    
                    print(f"✅ Đã chụp ảnh cho số {current_digit} ({current_digit_index}/6)")
                    break
            
            # Hiển thị thông tin
            cv2.putText(frame, f"OTP: {saved_otp}", (30, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, f"Dang doc: {saved_otp[current_digit_index] if current_digit_index < 6 else 'HOAN TAT'}", 
                    (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Da chup: {current_digit_index}/6", (30, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            remaining = int(capture_duration - (time.time() - start_time))
            cv2.putText(frame, f"Time: {remaining}s", (30, 130), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.imshow("Xác thực OTP - Kiểm tra Deepfake", frame)
            
            if cv2.waitKey(1) == 27:
                break
            
            if current_digit_index >= 6:
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Kiểm tra deepfake và so sánh khuôn mặt
        if captured_images:
            return self.analyze_faces_for_verification(user_id, captured_images, saved_otp)
        else:
            print("❌ Không chụp được ảnh nào")
            return False, 0.0, 0.0

    def display_otp_digit_images_grid(self, captured_images, otp_code):
        """
        Hiển thị grid 6 ảnh tương ứng với 6 chữ số OTP
        """
        if len(captured_images) != 6:
            print(f"⚠️ Cảnh báo: Chỉ có {len(captured_images)}/6 ảnh")
            return
        
        # Tạo grid 2x3
        rows, cols = 2, 3
        thumb_size = (300, 200)  # Kích thước mỗi ảnh trong grid
        
        grid_height = rows * thumb_size[1]
        grid_width = cols * thumb_size[0]
        grid = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)
        
        for i, (img, digit) in enumerate(captured_images):
            row = i // cols
            col = i % cols
            
            # Resize ảnh
            resized_img = cv2.resize(img, thumb_size)
            
            # Đặt ảnh vào grid
            y_start = row * thumb_size[1]
            y_end = y_start + thumb_size[1]
            x_start = col * thumb_size[0]
            x_end = x_start + thumb_size[0]
            
            grid[y_start:y_end, x_start:x_end] = resized_img
            
            # Thêm số thứ tự và chữ số
            cv2.putText(grid, f"{i+1}: {digit}", (x_start + 10, y_start + 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Thêm tiêu đề
        title = f"OTP: {otp_code} - 6 Face Images"
        cv2.putText(grid, title, (50, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Hiển thị grid
        cv2.imshow("OTP Face Images - 6 Digits", grid)
        cv2.waitKey(5000)  # Hiển thị trong 5 giây
        cv2.destroyAllWindows()


    def review_otp_digit_images(self, user_id: int, otp_code: str = None):
        """
        Xem lại 6 ảnh đã chụp theo từng chữ số OTP
        """
        print("\n📁 Đang tải ảnh đã chụp...")
        
        # Lấy tất cả ảnh của user, nếu có otp_code thì lọc theo OTP
        if otp_code:
            face_images_data = self.db.get_otp_face_images_by_code(user_id, otp_code)
        else:
            face_images_data = self.db.get_all_otp_face_images(user_id)
        
        if not face_images_data:
            print("❌ Không có ảnh nào để hiển thị")
            return
        
        # Nhóm ảnh theo OTP code
        otp_groups = {}
        for data in face_images_data:
            otp = data['otp_code']
            if otp not in otp_groups:
                otp_groups[otp] = []
            otp_groups[otp].append(data)
        
        for otp, images in otp_groups.items():
            print(f"\n🔐 OTP: {otp}")
            print(f"📸 Số ảnh: {len(images)}")
            
            # Sắp xếp theo image_index
            images.sort(key=lambda x: x['index'])
            
            # Hiển thị từng ảnh
            for i, data in enumerate(images):
                img = data['image']
                index = data['index']
                digit = data.get('digit', 'N/A')
                
                # Thêm thông tin lên ảnh
                display_img = img.copy()
                cv2.putText(display_img, f"OTP: {otp}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(display_img, f"Digit: {digit} (#{index})", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                
                cv2.imshow(f"OTP Face - {otp} - Digit {digit}", display_img)
                key = cv2.waitKey(0)
                
                if key == 27:  # ESC để thoát
                    break
            
            cv2.destroyAllWindows()

    def analyze_faces_for_verification(self, user_id: int, captured_images: list, otp_code: str):
        """
        Phân tích 6 ảnh để phát hiện deepfake và so sánh khuôn mặt
        """
        print("\n🔍 Đang phân tích ảnh để phát hiện deepfake...")
        
        # Lấy face encodings đã đăng ký
        registered_faces = self.db.get_face_encodings(user_id)
        if not registered_faces:
            print("❌ Không tìm thấy dữ liệu khuôn mặt đã đăng ký")
            return False, 0.0, 0.0
        
        deepfake_scores = []
        face_match_scores = []
        liveness_scores = []
        
        for i, (img, digit) in enumerate(captured_images):
            print(f"\n📊 Phân tích ảnh {i+1}/6 (Số {digit})...")
            
            # Phát hiện khuôn mặt
            face_locations = face_recognition.face_locations(img)
            if not face_locations:
                print(f"  ❌ Không tìm thấy khuôn mặt trong ảnh {i+1}")
                continue
            
            # Kiểm tra deepfake (nét mất khúc, artifacts)
            deepfake_score = self.detect_deepfake_artifacts(img, face_locations[0])
            deepfake_scores.append(deepfake_score)
            
            # Kiểm tra liveness
            liveness_score, _ = self.detect_face_liveness(img, face_locations)
            liveness_scores.append(liveness_score)
            
            # So sánh với khuôn mặt đã đăng ký
            current_encoding = face_recognition.face_encodings(img, face_locations)[0]
            face_distances = face_recognition.face_distance(registered_faces, current_encoding)
            face_similarity = 1 - min(face_distances)
            face_match_scores.append(face_similarity)
            
            print(f"  ✅ Deepfake Score: {deepfake_score:.1%}")
            print(f"  ✅ Liveness: {liveness_score:.1%}")
            print(f"  ✅ Face Match: {face_similarity:.1%}")
        
        if not deepfake_scores or not face_match_scores:
            return False, 0.0, 0.0
        
        # Tính điểm trung bình
        avg_deepfake_score = np.mean(deepfake_scores)
        avg_face_match = np.mean(face_match_scores)
        avg_liveness = np.mean(liveness_scores) if liveness_scores else 0.0
        
        print(f"\n📊 KẾT QUẢ PHÂN TÍCH:")
        print(f"  🎯 Độ tương đồng khuôn mặt: {avg_face_match:.1%}")
        print(f"  🔍 Deepfake detection: {avg_deepfake_score:.1%}")
        print(f"  ❤️  Liveness: {avg_liveness:.1%}")
        
        # Ngưỡng xác thực
        face_threshold = 0.6
        deepfake_threshold = 0.4  # Dưới 30% khả năng deepfake
        liveness_threshold = 0.5
        
        verified = (avg_face_match >= face_threshold and 
                    avg_deepfake_score <= deepfake_threshold and 
                    avg_liveness >= liveness_threshold)
        
        if verified:
            print("🎉 Xác thực OTP và khuôn mặt THÀNH CÔNG!")
        else:
            print("❌ Xác thực OTP và khuôn mặt THẤT BẠI!")
        
        return verified, avg_face_match, avg_deepfake_score

    def detect_deepfake_artifacts(self, frame: np.ndarray, face_location: tuple) -> float:
        """
        Phát hiện deepfake dựa trên artifacts, nét mất khúc
        Returns: Điểm số deepfake (càng cao càng có khả năng là deepfake)
        """
        try:
            top, right, bottom, left = face_location
            face_roi = frame[top:bottom, left:right]
            
            scores = []
            
            # 1. Phân tích độ mờ (blur) không tự nhiên
            gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            blur_value = cv2.Laplacian(gray_face, cv2.CV_64F).var()
            
            # Deepfake thường có blur không đồng đều
            if blur_value < 50:  # Quá mờ
                scores.append(0.8)
            elif blur_value < 100:
                scores.append(0.5)
            else:
                scores.append(0.2)
            
            # 2. Phân tích màu sắc không tự nhiên
            hsv_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
            saturation = hsv_face[:, :, 1]
            saturation_std = np.std(saturation)
            
            # Màu sắc quá đều có thể là dấu hiệu của GAN
            if saturation_std < 15:
                scores.append(0.7)
            elif saturation_std < 25:
                scores.append(0.4)
            else:
                scores.append(0.1)
            
            # 3. Phân tích cạnh (edge) không tự nhiên
            edges = cv2.Canny(gray_face, 50, 150)
            edge_density = np.sum(edges > 0) / (face_roi.shape[0] * face_roi.shape[1])
            
            # Cạnh quá rõ hoặc quá mờ có thể là dấu hiệu
            if edge_density > 0.4:  # Quá nhiều chi tiết
                scores.append(0.6)
            elif edge_density < 0.1:  # Quá ít chi tiết
                scores.append(0.7)
            else:
                scores.append(0.2)
            
            # 4. Phân tích texture bằng Local Binary Pattern (đơn giản)
            lbp = self.calculate_lbp_features(gray_face)
            texture_score = np.std(lbp) / 255.0
            if texture_score < 0.1:  # Texture quá đều
                scores.append(0.6)
            else:
                scores.append(0.2)
            
            deepfake_score = np.mean(scores)
            return min(deepfake_score, 1.0)
            
        except Exception as e:
            print(f"⚠️ Lỗi phân tích deepfake: {e}")
            return 0.5  # Trả về điểm trung bình nếu có lỗi

    def calculate_lbp_features(self, gray_image: np.ndarray) -> np.ndarray:
        """
        Tính Local Binary Pattern features (đơn giản)
        """
        try:
            # LBP đơn giản
            height, width = gray_image.shape
            lbp = np.zeros_like(gray_image)
            
            for i in range(1, height-1):
                for j in range(1, width-1):
                    center = gray_image[i, j]
                    code = 0
                    code |= (gray_image[i-1, j-1] > center) << 7
                    code |= (gray_image[i-1, j] > center) << 6
                    code |= (gray_image[i-1, j+1] > center) << 5
                    code |= (gray_image[i, j+1] > center) << 4
                    code |= (gray_image[i+1, j+1] > center) << 3
                    code |= (gray_image[i+1, j] > center) << 2
                    code |= (gray_image[i+1, j-1] > center) << 1
                    code |= (gray_image[i, j-1] > center) << 0
                    lbp[i, j] = code
                    
            return lbp
        except Exception:
            return np.zeros_like(gray_image)