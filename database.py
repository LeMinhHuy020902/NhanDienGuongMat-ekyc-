import psycopg2
import pickle
import numpy as np
import cv2
from typing import Optional, List, Tuple

class EKYCDatabase:
    def __init__(self, dbname='ekyc_system', user='postgres', password='bon123', host='localhost'):
        """
        Kết nối tới PostgreSQL database
        """
        self.conn = psycopg2.connect(
            dbname=dbname, user=user, password=password, host=host
        )
        # Đặt autocommit để tránh lỗi transaction
        self.conn.autocommit = True

    # ================================
    # 1. Thêm người dùng mới
    # ================================
    def add_user(self, username: str, password: str, email: Optional[str] = None) -> int:
        """
        Thêm user mới vào bảng users và trả về user_id.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (username, password, email)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (username, password, email))
                user_id = cur.fetchone()[0]
                return user_id
        except Exception as e:
            print(f"❌ Lỗi thêm user: {e}")
            # Rollback và thử lại với transaction mới
            self.conn.rollback()
            raise e

    # ================================
    # 2. Lưu voice print - PHIÊN BẢN MỚI: LƯU NHIỀU MẪU
    # ================================
    def save_voice_prints(self, user_id: int, features_list: List[np.ndarray], sample_rate: int):
        """
        Lưu nhiều voice features (3 mẫu) và sample_rate
        """
        try:
            with self.conn.cursor() as cur:
                # Xóa các mẫu cũ trước khi lưu mẫu mới
                cur.execute("DELETE FROM voice_prints WHERE user_id = %s", (user_id,))
                
                # Lưu từng mẫu riêng biệt
                for i, features in enumerate(features_list):
                    # Đóng gói features và sample_rate
                    voice_data = {
                        'features': np.asarray(features),
                        'sample_rate': sample_rate,
                        'sample_index': i  # Đánh số thứ tự mẫu
                    }
                    data = pickle.dumps(voice_data)
                    
                    cur.execute("""
                        INSERT INTO voice_prints (user_id, voice_print, sample_rate)
                        VALUES (%s, %s, %s)
                    """, (user_id, data, sample_rate))
                    
            print(f"✅ Đã lưu {len(features_list)} mẫu voice print cho user {user_id}")
            
        except Exception as e:
            print(f"❌ Lỗi lưu voice prints: {e}")
            self.conn.rollback()
            raise e

    def get_voice_prints(self, user_id: int) -> Tuple[List[np.ndarray], int]:
        """
        Lấy tất cả voice features và sample_rate
        Trả về: (danh_sách_features, sample_rate)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT voice_print, sample_rate 
                    FROM voice_prints 
                    WHERE user_id = %s
                    ORDER BY created_at ASC
                """, (user_id,))
                rows = cur.fetchall()
                
                if not rows:
                    return [], 0
                
                features_list = []
                sample_rate = rows[0][1]  # Lấy sample_rate từ bản ghi đầu tiên
                
                for row in rows:
                    voice_data_bytes, sr = row
                    try:
                        # Giải nén dữ liệu
                        voice_data = pickle.loads(voice_data_bytes)
                        if isinstance(voice_data, dict) and 'features' in voice_data:
                            features = voice_data['features']
                            features_list.append(features)
                        else:
                            # Dữ liệu cũ chỉ có features
                            features_list.append(voice_data)
                    except Exception as e:
                        print(f"❌ Lỗi giải nén voice data: {e}")
                        continue
                
                return features_list, sample_rate
                
        except Exception as e:
            print(f"❌ Lỗi lấy voice prints: {e}")
            return [], 0

    # ================================
    # 3. Hàm cũ để tương thích ngược (CHO PHÉP CODE CŨ HOẠT ĐỘNG)
    # ================================
    def save_voice_print(self, user_id: int, voice_features: np.ndarray, sample_rate: int):
        """
        Lưu voice features (1 mẫu) - Hàm cũ để tương thích
        """
        return self.save_voice_prints(user_id, [voice_features], sample_rate)

    def get_voice_print(self, user_id: int) -> Optional[Tuple[np.ndarray, int]]:
        """
        Lấy voice features (mẫu đầu tiên) - Hàm cũ để tương thích
        """
        features_list, sample_rate = self.get_voice_prints(user_id)
        if features_list:
            return features_list[0], sample_rate
        return None

    # ================================
    # 4. Lưu 3 face encodings (face-print)
    # ================================
    def save_face_encodings(self, user_id: int, encodings: List[np.ndarray], angles: Optional[List[str]] = None):
        """
        Lưu nhiều face encodings (trái, chính diện, phải)
        """
        try:
            if angles is None:
                angles = [None] * len(encodings)

            with self.conn.cursor() as cur:
                for enc, angle in zip(encodings, angles):
                    data = pickle.dumps(np.asarray(enc))
                    cur.execute("""
                        INSERT INTO face_encodings (user_id, face_encoding, angle)
                        VALUES (%s, %s, %s)
                    """, (user_id, data, angle))
            print(f"✅ Đã lưu {len(encodings)} face encodings cho user {user_id}")
            
        except Exception as e:
            print(f"❌ Lỗi lưu face encodings: {e}")
            self.conn.rollback()
            raise e

    def get_face_encodings(self, user_id: int) -> List[np.ndarray]:
        """
        Lấy danh sách các face encoding đã lưu
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT face_encoding 
                    FROM face_encodings 
                    WHERE user_id = %s 
                    ORDER BY angle
                """, (user_id,))
                rows = cur.fetchall()
                encodings = []
                for r in rows:
                    enc = pickle.loads(r[0])
                    encodings.append(np.asarray(enc))
                return encodings
                
        except Exception as e:
            print(f"❌ Lỗi lấy face encodings: {e}")
            return []

    def get_face_encodings_by_angle(self, user_id: int, angle: str) -> List[np.ndarray]:
        """
        Lấy face encoding theo góc cụ thể
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT face_encoding 
                    FROM face_encodings 
                    WHERE user_id = %s AND angle = %s
                """, (user_id, angle))
                rows = cur.fetchall()
                encodings = []
                for r in rows:
                    enc = pickle.loads(r[0])
                    encodings.append(np.asarray(enc))
                return encodings
                
        except Exception as e:
            print(f"❌ Lỗi lấy face encodings theo góc: {e}")
            return []

    # ================================
    # 5. Ghi log KYC
    # ================================
    def log_kyc_session(self, user_id: int, result: bool, face_score: float, voice_score: float):
        """
        Ghi lại kết quả xác thực
        Lưu ý: face_score và voice_score bây giờ là combined scores (đã bao gồm liveness)
        """
        try:
            with self.conn.cursor() as cur:
                # ép kiểu bool về bool chuẩn của Python
                result = bool(result)
                cur.execute("""
                    INSERT INTO kyc_sessions (user_id, result, face_score, voice_score)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, result, float(face_score), float(voice_score)))
            # Không in để tránh spam trong output
        except Exception as e:
            print(f"❌ Lỗi ghi log KYC: {e}")
            self.conn.rollback()
            
    # ================================
    # 6. Kiểm tra và tạo bảng nếu cần
    # ================================
    def check_and_create_tables(self):
        """
        Kiểm tra và tạo các bảng cần thiết nếu chưa tồn tại
        """
        try:
            with self.conn.cursor() as cur:
                # Kiểm tra xem bảng voice_prints có tồn tại không
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'voice_prints'
                    );
                """)
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    print("⚠️ Bảng voice_prints không tồn tại, đang tạo bảng mới...")
                    cur.execute("""
                        CREATE TABLE voice_prints (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id),
                            voice_print BYTEA NOT NULL,
                            sample_rate INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    print("✅ Đã tạo bảng voice_prints")
                    
        except Exception as e:
            print(f"❌ Lỗi kiểm tra/ tạo bảng: {e}")
            self.conn.rollback()


    def save_otp_face_images_sequence(self, user_id: int, otp_code: str, face_images: list):
        """
        Lưu 6 ảnh khuôn mặt tương ứng với 6 chữ số OTP
        """
        try:
            success_count = 0
            with self.conn.cursor() as cur:
                for i, (face_image, digit) in enumerate(face_images):
                    # Chuyển ảnh thành dạng byte để lưu vào DB
                    is_success, buffer = cv2.imencode(".jpg", face_image)
                    if not is_success:
                        print(f"❌ Lỗi encode ảnh khuôn mặt cho số {digit}.")
                        continue

                    image_bytes = buffer.tobytes()

                    cur.execute("""
                        INSERT INTO user_otp_faces (user_id, otp_code, face_image, image_index, digit)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, otp_code, image_bytes, i+1, digit))
                    success_count += 1
            
            print(f"✅ Đã lưu {success_count}/6 ảnh khuôn mặt cho OTP '{otp_code}'")
            return success_count == 6
        except Exception as e:
            print(f"❌ Lỗi lưu ảnh khuôn mặt sequence: {e}")
            self.conn.rollback()
            return False

# Cập nhật phương thức create_otp_face_table để thêm cột digit
    def create_otp_face_table(self):
        """
        Tạo bảng lưu trữ OTP và ảnh khuôn mặt khi đọc OTP
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_otp_faces (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        otp_code VARCHAR(10) NOT NULL,
                        face_image BYTEA NOT NULL,
                        image_index INTEGER DEFAULT 1,
                        digit VARCHAR(1),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            print("✅ Đã tạo/kiểm tra bảng user_otp_faces")
        except Exception as e:
            print(f"❌ Lỗi tạo bảng OTP faces: {e}")


    def get_otp_face_images_by_code(self, user_id: int, otp_code: str):
        """
        Lấy ảnh khuôn mặt theo OTP code cụ thể
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT face_image, image_index, digit, otp_code
                    FROM user_otp_faces 
                    WHERE user_id = %s AND otp_code = %s
                    ORDER BY image_index ASC
                """, (user_id, otp_code))
                
                rows = cur.fetchall()
                face_images = []
                for row in rows:
                    image_bytes, image_index, digit, otp_code = row
                    # Chuyển bytes trở lại ảnh
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    face_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    face_images.append({
                        'image': face_image,
                        'index': image_index,
                        'digit': digit,
                        'otp_code': otp_code
                    })
                return face_images
        except Exception as e:
            print(f"❌ Lỗi lấy ảnh khuôn mặt theo OTP: {e}")
            return []

    # ================================
    # 7. Đóng kết nối
    # ================================
    def close(self):
        self.conn.close()

    def get_latest_otp_for_user(self, user_id: int):
        """
        Lấy OTP mới nhất đã lưu cho user (dùng trong xác thực)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT otp_code, created_at
                    FROM user_otp_faces 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (user_id,))
                result = cur.fetchone()
                if result:
                    return result[0]  # Trả về OTP code
                return None
        except Exception as e:
            print(f"❌ Lỗi lấy OTP: {e}")
            return None

    def get_otp_face_count(self, user_id: int) -> int:
        """
        Đếm số lượng ảnh khuôn mặt OTP đã lưu cho một người dùng
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM user_otp_faces
                    WHERE user_id = %s
                """, (user_id,))
                result = cur.fetchone()
                return result[0] if result else 0
        except Exception as e:
            print(f"❌ Lỗi khi đếm số lượng ảnh OTP: {e}")
            return 0