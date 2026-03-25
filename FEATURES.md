# 🎯 Tính Năng Hệ Thống EKYC

## 📋 Tổng Quan

Hệ thống EKYC (Electronic Know Your Customer) tích hợp **nhận diện khuôn mặt** và **nhận diện giọng nói** với khả năng **phát hiện liveness** để chống giả mạo.

---

## 🔐 Các Tính Năng Chính

### 1️⃣ **Nhận Diện Khuôn Mặt (Face Recognition)**

#### Đăng Ký
- ✅ Chụp **3 góc mặt**: Trái, Chính diện, Phải
- ✅ Lưu 3 face encodings vào database
- ✅ Kiểm tra **face liveness** real-time trong quá trình chụp
- ✅ Cảnh báo khi phát hiện ảnh in/video

#### Xác Thực
- ✅ So khớp với 3 góc mặt đã lưu
- ✅ Ngưỡng: **70%** similarity
- ✅ Kết hợp **70% similarity + 30% liveness** để tính combined score
- ✅ Hiển thị real-time: Match score, Liveness score, Combined score

#### Face Liveness Detection
```
4 Phương Pháp Phát Hiện:
├─ 1. Texture Analysis (Laplacian Variance)
│  └─ Phát hiện ảnh in quá mịn
├─ 2. Aspect Ratio Analysis
│  └─ Phát hiện tỷ lệ khuôn mặt bất thường
├─ 3. Edge Detection (Canny)
│  └─ Phát hiện khung viền của ảnh in
└─ 4. Color Analysis (HSV)
   └─ Phát hiện màu da không tự nhiên
```

---

### 2️⃣ **Nhận Diện Giọng Nói (Voice Recognition)**

#### Đăng Ký
- ✅ Thu âm **3 mẫu giọng** với prompts khác nhau
- ✅ Phát ngẫu nhiên **6 chữ số** để chống replay
- ✅ Trích xuất **20+ đặc trưng** sinh trắc học
- ✅ Kiểm tra **voice liveness** cho mỗi mẫu
- ✅ Lưu median features vào database

#### Xác Thực
- ✅ **OTP 6 chữ số** ngẫu nhiên (chống replay attack)
- ✅ **Timeout 60 giây** để đọc OTP
- ✅ Thu âm và phân tích giọng nói
- ✅ So khớp với voice print đã lưu
- ✅ Sử dụng **6 thuật toán** khác nhau
- ✅ Kết hợp **70% similarity + 30% liveness**
- ✅ **Auto-retry**: Tự động tạo OTP mới nếu thất bại (tối đa 3 lần)
- ✅ Ngưỡng: Combined >= **75%** và Liveness >= **50%**
- ✅ Cho phép **hủy bỏ** bằng phím 'q'

#### Voice Feature Extraction
```
Đặc Trưng Sinh Trắc Học:
├─ MFCC (20 coefficients)
├─ MFCC Covariance (10 values)
├─ Mel Spectrogram (40 mels)
├─ Chroma Features (12 values)
├─ Spectral Centroid
├─ Pitch (mean, std, range)
├─ Spectral Rolloff
├─ HNR (Harmonics-to-Noise Ratio)
├─ ZCR (Zero Crossing Rate)
└─ RMS (Root Mean Square Energy)
```

#### Voice Similarity Algorithms
```
6 Thuật Toán So Khớp:
├─ DTW (Dynamic Time Warping) - 12%
├─ EMD (Earth Mover's Distance) - 20%
├─ Cosine Similarity - 18%
├─ Spearman Correlation - 10%
├─ Structural Similarity - 10%
└─ Spectral Pattern Similarity - 30%
```

#### Voice Liveness Detection
```
6 Phương Pháp Phát Hiện:
├─ 1. Spectral Centroid Variance
│  └─ Phát hiện phổ TTS quá đều
├─ 2. Pitch Variability
│  └─ Phát hiện cao độ TTS quá ổn định
├─ 3. ZCR Pattern Variance
│  └─ Phát hiện biến đổi ZCR thấp
├─ 4. Spectral Rolloff Variance
│  └─ Phát hiện rolloff bất thường
├─ 5. HNR (Harmonics-to-Noise Ratio)
│  └─ Phát hiện tỷ lệ hài âm bất thường
└─ 6. Energy Variation
   └─ Phát hiện năng lượng quá ổn định
```

---

### 3️⃣ **Chống Giả Mạo (Anti-Spoofing)**

#### Face Anti-Spoofing
- ⚠️ Phát hiện **ảnh in 2D**
- ⚠️ Phát hiện **video replay**
- ⚠️ Phát hiện **deepfake** cơ bản
- ✅ Cảnh báo chi tiết cho từng loại tấn công

#### Voice Anti-Spoofing
- ⚠️ Phát hiện **Text-to-Speech (TTS)**
- ⚠️ Phát hiện **voice replay**
- ⚠️ Phát hiện **voice deepfake** cơ bản
- ✅ Cảnh báo với lý do cụ thể

#### Multi-Layer Protection
```
Lớp Bảo Vệ:
├─ Lớp 1: Feature Extraction
│  └─ Trích xuất đặc trưng sinh trắc học
├─ Lớp 2: Liveness Detection
│  └─ Phát hiện người thật vs giả mạo
├─ Lớp 3: Combined Scoring
│  └─ Kết hợp similarity + liveness
├─ Lớp 4: Threshold Check
│  └─ Ngưỡng kép (combined + liveness)
└─ Lớp 5: Database Logging
   └─ Ghi lại mọi session để audit
```

---

### 4️⃣ **Database & Logging**

#### Schema
```
4 Bảng Chính:
├─ users
│  ├─ id, username, password, email
│  └─ created_at
├─ face_encodings
│  ├─ id, user_id, face_encoding (BYTEA)
│  ├─ angle (left/front/right)
│  └─ created_at
├─ voice_prints
│  ├─ user_id, voice_print (BYTEA)
│  ├─ sample_rate
│  └─ created_at
└─ kyc_sessions
   ├─ id, user_id
   ├─ result (boolean)
   ├─ face_score, voice_score
   └─ created_at
```

#### Logging
- ✅ Ghi log **mọi session** xác thực
- ✅ Lưu **face_score** và **voice_score**
- ✅ Lưu **kết quả** thành công/thất bại
- ✅ Timestamp đầy đủ

---

## 🎯 Flow Hoạt Động

### Đăng Ký (Registration)
```
1. User nhập thông tin → Tạo user_id
2. Chụp 3 góc mặt:
   ├─ Realtime liveness check
   ├─ Cảnh báo nếu < 50%
   └─ Lưu 3 encodings
3. Thu 3 mẫu giọng:
   ├─ Random 6 digits
   ├─ Liveness check mỗi mẫu
   ├─ Cảnh báo nếu < 50%
   └─ Lưu median features
4. Hoàn tất đăng ký
```

### Xác Thực (Verification)
```
1. Nhập username → Lấy user_id
2. Face Verification:
   ├─ So khớp với 3 encodings
   ├─ Liveness detection
   ├─ Combined score >= 70%
   └─ Liveness >= 50%
3. Voice Verification với OTP:
   ├─ 🔐 Tạo OTP 6 chữ số ngẫu nhiên
   ├─ ⏱️ Hiển thị OTP và chờ 60 giây
   ├─ 🎤 Thu âm giọng người dùng
   ├─ So khớp với voice print
   ├─ Liveness detection
   ├─ Combined score >= 75% và Liveness >= 50%
   ├─ Nếu fail → Tạo OTP mới (max 3 lần)
   ├─ Nếu user hủy → Return False
   └─ ✅ Pass nếu cả similarity + liveness đạt
4. Kết quả cuối cùng:
   ├─ Cả 2 phải pass
   └─ Log session vào DB
```

---

## 📊 Metrics & Scoring

### Face Scores
- **Similarity**: 0-1 (từ face_distance)
- **Liveness**: 0-1 (từ 4 phương pháp)
- **Combined**: 0.7 × Similarity + 0.3 × Liveness

### Voice Scores
- **Similarity**: 0-1 (từ 6 thuật toán)
- **Liveness**: 0-1 (từ 6 phương pháp)
- **Combined**: 0.7 × Similarity + 0.3 × Liveness

### Thresholds
| Metric | Threshold | Mô Tả |
|--------|-----------|-------|
| Face Combined | >= 0.7 | 70% combined score |
| Face Liveness | >= 0.5 | 50% liveness |
| Voice Combined | >= 0.75 | 75% combined score |
| Voice Liveness | >= 0.5 | 50% liveness |
| Overall | Both pass | Cả 2 phải đạt |

---

## 🔧 Technical Details

### Dependencies
```
Computer Vision:
├─ opencv-python >= 4.8.0
├─ face-recognition >= 1.3.0
└─ dlib >= 19.24.0

Audio Processing:
├─ SpeechRecognition >= 3.10.0
├─ librosa >= 0.10.0
├─ noisereduce >= 3.0.0
└─ PyAudio >= 0.2.11

ML/Signal:
├─ numpy >= 1.24.0
├─ scipy >= 1.10.0
└─ scikit-learn >= 1.3.0

Database:
└─ psycopg2-binary >= 2.9.0
```

### Performance
- **Face Recognition**: ~30fps (realtime)
- **Voice Processing**: ~1s/mẫu
- **Overall Verification**: ~5-10s
- **Liveness Detection**: Realtime, < 50ms

---

## ✨ Điểm Nổi Bật

1. ✅ **Multi-modal**: Khuôn mặt + Giọng nói
2. ✅ **Anti-spoofing**: Liveness detection cho cả 2
3. ✅ **Real-time**: Phát hiện ngay khi chụp/thu
4. ✅ **Detailed**: Hiển thị điểm số chi tiết
5. ✅ **Robust**: Nhiều lớp bảo vệ
6. ✅ **Logged**: Ghi lại mọi session
7. ✅ **User-friendly**: Interface rõ ràng
8. ✅ **Extensible**: Dễ mở rộng thêm phương pháp

---

## 🚀 Sử Dụng

```bash
# Cài đặt
pip install -r requirements.txt

# Setup database
psql -U postgres -f "Database DoAn.txt"

# Chạy chương trình
python main_ekyc.py
```

### 📋 Menu Chính
Hệ thống cung cấp 4 phương thức xác thực:
1. **📝 Đăng ký**: Tạo tài khoản mới (Face + Voice)
2. **🔍 Xác thực EKYC**: Đầy đủ Face + Voice với OTP
3. **⚡ Xác thực nhanh**: Chỉ Face recognition
4. **🔐 Nhận diện bằng OTP**: Chỉ Voice recognition với OTP

---

## 📝 Chú Ý

⚠️ **Yêu Cầu Hệ Thống:**
- Camera (webcam)
- Microphone
- PostgreSQL database
- Python 3.8+
- 8GB+ RAM (khuyến nghị)

⚠️ **Limitations:**
- Liveness detection cơ bản, chưa dùng deep learning
- Không hỗ trợ multi-face detection
- Chỉ hỗ trợ 1 ngôn ngữ (tiếng Việt)
- Cần môi trường đủ sáng và ít tiếng ồn

⚠️ **Security:**
- Không lưu password dạng plaintext (nên hash)
- Không có encryption cho biometric data
- Không có rate limiting
- Nên thêm thêm các lớp bảo mật khác cho production

---

## 🎓 Kiến Thức Áp Dụng

- Computer Vision (OpenCV, face recognition)
- Audio Signal Processing (librosa, MFCC)
- Machine Learning (feature extraction, similarity)
- Database Design (PostgreSQL, indexing)
- Biometric Authentication
- Anti-spoofing Techniques
- Multi-factor Authentication

