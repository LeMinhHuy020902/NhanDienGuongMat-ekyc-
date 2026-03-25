


# 🔐 Hệ Thống EKYC - Nhận Diện Khuôn Mặt & Giọng Nói với Liveness Detection

Hệ thống EKYC (Electronic Know Your Customer) tích hợp nhận diện khuôn mặt và giọng nói với khả năng phát hiện "Liveness" (người thật vs giả mạo).

## ✨ Tính Năng Chính

### 1️⃣ Nhận Diện Khuôn Mặt (Face Recognition)
- 📷 Chụp 3 góc mặt: Trái, Chính diện, Phải
- 🔍 So khớp độ tương đồng: 70% ngưỡng chuẩn
- ✅ **Face Liveness Detection**: Phát hiện người thật vs ảnh in/ảnh video
  - Texture Analysis (Laplacian variance)
  - Face Aspect Ratio
  - Edge Detection
  - Color Analysis

### 2️⃣ Nhận Diện Giọng Nói (Voice Recognition)
- 🎤 Trích xuất 20+ đặc trưng sinh trắc học:
  - MFCC (Mel-frequency Cepstral Coefficients)
  - Mel Spectrogram
  - Chroma Features
  - Pitch, Harmonics, Energy, Zero Crossing Rate
- 🔄 Đa thuật toán so khớp: DTW, EMD, Cosine Similarity, Spearman
- ✅ **Voice Liveness Detection**: Phát hiện giọng thật vs Text-to-Speech
  - Spectral Centroid Variation
  - Pitch Variability
  - ZCR Pattern Analysis
  - Harmonics-to-Noise Ratio (HNR)
  - Energy Variation

### 3️⃣ Bảo Mật Chống Giả Mạo
- ⚠️ Cảnh báo khi phát hiện dấu hiệu giả mạo
- 🚫 Từ chối đăng ký/xác thực nếu liveness score < 50%
- 📊 Hiển thị điểm số chi tiết cho từng phương thức
- 🔒 Kết hợp nhiều phương pháp phát hiện để tăng độ tin cậy

### 4️⃣ Database & Logging
- 🗄️ PostgreSQL database với schema đầy đủ
- 📝 Lưu trữ: Face encodings, Voice prints, User info
- 📊 Log KYC sessions với face_score và voice_score
- 🔄 Hỗ trợ query và quản lý dữ liệu người dùng

## 🛠️ Cài Đặt

### 1. Clone Repository
```bash
git clone <repository-url>
cd pyproject2
```

### 2. Tạo Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# hoặc
source venv/bin/activate  # Linux/Mac
```

### 3. Cài Đặt Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Database
```sql
-- Chạy file "Database DoAn.txt" trong PostgreSQL
-- Đảm bảo database 'ekyc_system' đã được tạo
```

### 5. Cấu Hình Database
Chỉnh sửa file `database.py` dòng 11 nếu cần:
```python
def __init__(self, dbname='ekyc_system', user='postgres', password='tkaido', host='localhost'):
```

## 🚀 Sử Dụng

### Chạy Chương Trình
```bash
python main_ekyc.py
```

### Menu Chính
```
🔐 HỆ THỐNG EKYC KHUÔN MẶT + GIỌNG NÓI 🔐

📋 MENU CHÍNH:
 1. 📝 Đăng ký người dùng mới
 2. 🔍 Xác thực EKYC (Face + Voice)
 3. ⚡ Xác thực nhanh (khuôn mặt)
 4. 🔐 Nhận diện bằng OTP (giọng nói)
 5. 🚪 Thoát

👉 Chọn (1-5):
```

### 1. Đăng Ký Người Dùng Mới
1. Nhập username, password, email
2. Chụp 3 góc mặt (trái, chính diện, phải)
   - **Liveness check**: Tự động kiểm tra người thật
   - Nhấn SPACE để chụp, ESC để hủy
3. Đăng ký giọng nói với 3 mẫu
   - Phát ngẫu nhiên 6 chữ số
   - **Liveness check**: Phát hiện TTS
4. Hoàn tất đăng ký

### 2. Xác Thực EKYC
1. Nhập username
2. Xác thực khuôn mặt:
   - Độ khớp: Similarity score
   - Liveness: Người thật score
   - Combined score >= 70% ✅
3. Xác thực giọng nói với OTP:
   - 🔐 Hiển thị mã OTP 6 chữ số ngẫu nhiên
   - ⏱️ Có 60 giây để đọc mã OTP
   - 🎤 Thu âm và phân tích giọng nói
   - ✅ Độ khớp sinh trắc học + Liveness detection
   - 🔄 Nếu sai, tự động tạo mã OTP mới (tối đa 3 lần)
   - ❌ Người dùng có thể nhấn 'q' để thoát
   - Combined score >= 75% & Liveness >= 50% ✅
4. Kết quả cuối cùng

### 3. Xác Thực Nhanh
- Chỉ kiểm tra khuôn mặt
- Không kiểm tra giọng nói

### 4. Nhận Diện Bằng OTP
- Chỉ kiểm tra giọng nói với mã OTP
- Không kiểm tra khuôn mặt
- Phù hợp cho các trường hợp đơn giản, nhanh chóng
- Quy trình tương tự như trong option 2 (phần voice verification)

## 📊 Cơ Chế Liveness Detection

### Face Liveness (Người Thật)
| Metric | Mô Tả | Ngưỡng |
|--------|-------|--------|
| **Texture** | Laplacian variance | < 100: Nghi ngờ, < 200: Trung bình, > 200: OK |
| **Aspect Ratio** | Tỷ lệ khuôn mặt | 0.7-0.9: Tự nhiên |
| **Edge Density** | Mật độ cạnh | > 0.3: Tốt |
| **Color Hue** | Màu da | 0-50: Hợp lý |

### Voice Liveness (Giọng Thật)
| Metric | Mô Tả | Ngưỡng |
|--------|-------|--------|
| **Spectral Variance** | Biến đổi phổ tần số | > 100,000: Tốt |
| **Pitch Variance** | Biến đổi cao độ | > 500: Tốt, > 200: OK |
| **ZCR Variance** | Biến đổi ZCR | > 0.01: Tốt |
| **HNR** | Tỷ lệ hài âm | 2.0-20.0: Bình thường |
| **Energy Variance** | Biến đổi năng lượng | > 0.001: Tốt |

## 🗄️ Database Schema

```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Face Encodings (3 góc)
CREATE TABLE face_encodings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    face_encoding BYTEA NOT NULL,
    angle VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Voice Prints
CREATE TABLE voice_prints (
    user_id INTEGER REFERENCES users(id),
    voice_print BYTEA NOT NULL,
    sample_rate INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- KYC Logs
CREATE TABLE kyc_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    result BOOLEAN,
    face_score FLOAT,
    voice_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 📦 Dependencies

- **Computer Vision**: OpenCV, face-recognition, dlib
- **Audio Processing**: SpeechRecognition, librosa, noisereduce
- **Machine Learning**: NumPy, SciPy, scikit-learn
- **Database**: PostgreSQL (psycopg2)

Xem `requirements.txt` để biết chi tiết.

## ⚙️ Cấu Hình

### Ngưỡng Xác Thực
```python
# Face Recognition
FACE_THRESHOLD = 0.7  # 70%
FACE_LIVENESS_THRESHOLD = 0.5  # 50%

# Voice Recognition
VOICE_THRESHOLD = 0.75  # 75% (combined)
VOICE_LIVENESS_THRESHOLD = 0.5  # 50%

# Combined Score
COMBINED_FACE_WEIGHT = 0.7  # Face
COMBINED_VOICE_WEIGHT = 0.3  # Liveness
```

## 🔒 Bảo Mật

- ✅ Phát hiện ảnh in 2D, video replay
- ✅ Phát hiện giọng TTS, deepfake voice
- ✅ Multi-factor authentication (Face + Voice)
- ✅ Liveness detection real-time
- ✅ Logging đầy đủ mọi session

## 📝 Lưu Ý

1. **Camera**: Cần webcam để chụp khuôn mặt
2. **Microphone**: Cần mic để ghi âm giọng nói
3. **Môi trường**: Ánh sáng tốt, ít tạp âm
4. **Database**: Đảm bảo PostgreSQL đang chạy
5. **Dlib**: Có thể cần compile từ source trên một số hệ thống

## 🐛 Troubleshooting

### Lỗi dlib installation
```bash
# Windows: Download wheel từ unofficial binaries
pip install dlib-binary

# Linux: Cài đặt dependencies
sudo apt-get install build-essential cmake
pip install dlib
```

### Lỗi PyAudio
```bash
# Windows
pip install pipwin
pipwin install pyaudio

# Linux
sudo apt-get install portaudio19-dev python3-pyaudio
```

### Lỗi kết nối Database
- Kiểm tra PostgreSQL đang chạy
- Kiểm tra thông tin đăng nhập trong `database.py`
- Đảm bảo database `ekyc_system` đã được tạo

## 👥 Tác Giả
2280603117 - Trần Tuấn Thịnh 2280601153 - Lê Minh Huy 2280601948 - Nguyễn Nhật Minh
Được phát triển cho dự án Đồ Án - Hệ Thống EKYC

## 📄 License

MIT License

