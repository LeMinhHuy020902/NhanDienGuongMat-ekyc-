import os
import tempfile
import random
import re
from typing import Tuple, List

import numpy as np
import soundfile as sf
import librosa
import noisereduce as nr
import speech_recognition as sr
import torch
import torchaudio

# liveness / basic audio analysis deps
from scipy.stats import pearsonr  

# DB wrapper from your project
from database import EKYCDatabase

# SpeechBrain ECAPA-TDNN for speaker verification
try:
    from speechbrain.pretrained import SpeakerRecognition
    SPEECHBRAIN_AVAILABLE = True
except Exception as e:
    SPEECHBRAIN_AVAILABLE = False
    SpeakerRecognition = None
    print("⚠️ SpeechBrain import failed:", e)
    print("   Please install speechbrain: pip install speechbrain")

# Whisper for offline ASR (used in your verify flow)
try:
    import whisper
    WHISPER_AVAILABLE = True
except Exception:
    WHISPER_AVAILABLE = False
    whisper = None


class VoiceVerification:
    """
    Voice verification module using ECAPA-TDNN (SpeechBrain) embeddings.
    Provides:
      - enroll_voice_biometric(user_id, num_samples=3)
      - verify_voice_biometric(user_id)  -> (success:bool, best_similarity:float, liveness_score:float)
      - detect_voice_liveness(audio, sr)  -> (score, warnings)
      - detect_voice_spoofing(audio, sr)  -> (spoof_score, is_bonafide:bool, warnings)
    """

    TARGET_SR = 16000  # ECAPA-TDNN expects 16k audio

    def __init__(self):
        if not SPEECHBRAIN_AVAILABLE:
            raise ImportError("SpeechBrain is required. Install it with: pip install speechbrain")
        self.db = EKYCDatabase()
        self.recognizer = sr.Recognizer()
        
        # Load ECAPA-TDNN model for speaker verification
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔧 Đang tải ECAPA-TDNN model trên {self.device}...")
        try:
            self.speaker_model = SpeakerRecognition.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb",
                run_opts={"device": self.device}
            )
            print("✅ Đã tải ECAPA-TDNN model thành công")
        except Exception as e:
            print(f"⚠️ Không thể tải ECAPA-TDNN từ HuggingFace: {e}")
            print("   Thử tải từ source khác hoặc kiểm tra kết nối mạng...")
            raise
        
        # Anti-spoofing thresholds
        self.enroll_samples_required = 3
        self.verification_threshold = 0.70  # Higher threshold for better security (ECAPA-TDNN scale)
        self.liveness_threshold = 0.50
        self.spoofing_threshold = 0.40  # Lower = more strict anti-spoofing

    # -------------------------
    # Audio preprocessing
    # -------------------------
    def preprocess_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        - Noise reduction (noisereduce)
        - Trim silence
        - Normalize amplitude to [-1, 1]
        """
        try:
            # Ensure float32
            y = np.asarray(audio_data, dtype=np.float32)

            # If audio recorded as int16 in [-32768,32767], scale
            if y.dtype == np.int16 or np.max(np.abs(y)) > 1.5:
                # convert from int16-like range
                max_abs = np.max(np.abs(y)) if np.max(np.abs(y)) > 0 else 1.0
                y = y / float(max_abs)

            # Noise reduction (try/except to be robust)
            try:
                y_nr = nr.reduce_noise(y=y, sr=sample_rate, prop_decrease=0.5)
            except Exception:
                y_nr = y

            # Trim leading/trailing silence
            try:
                y_trim, _ = librosa.effects.trim(y_nr, top_db=25)
            except Exception:
                y_trim = y_nr

            # Normalize peak to 0.99
            peak = np.max(np.abs(y_trim)) if np.max(np.abs(y_trim)) > 0 else 1.0
            y_norm = y_trim / peak * 0.99

            return y_norm.astype(np.float32)
        except Exception as e:
            print(f"⚠️ preprocess_audio error: {e}")
            # fallback: return raw scaled float32
            y = np.asarray(audio_data, dtype=np.float32)
            max_abs = np.max(np.abs(y)) if np.max(np.abs(y)) > 0 else 1.0
            return (y / max_abs * 0.99).astype(np.float32)

    def resample_audio(self, audio: np.ndarray, orig_sr: int) -> np.ndarray:
        """
        Resample audio to TARGET_SR (16000) for ECAPA-TDNN.
        """
        if orig_sr == self.TARGET_SR:
            return audio
        try:
            y_res = librosa.resample(audio, orig_sr=orig_sr, target_sr=self.TARGET_SR)
            return y_res.astype(np.float32)
        except Exception as e:
            print("⚠️ Resampling failed:", e)
            # fallback: simple numpy interpolation
            ratio = float(self.TARGET_SR) / float(orig_sr)
            new_len = int(len(audio) * ratio)
            y_res = np.interp(
                np.linspace(0, len(audio) - 1, new_len),
                np.arange(len(audio)),
                audio
            )
            return y_res.astype(np.float32)

    def record_voice_sample(self, duration=5):
        """
        Record from microphone using speech_recognition library.
        Returns (audio_numpy_float32, sample_rate)
        """
        with sr.Microphone() as source:
            print(f"🎤 Hãy nói tự nhiên trong {duration} giây (nội dung bên trên)")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=duration)
        # extract raw bytes and convert to float32
        raw_bytes = audio.get_raw_data()
        sample_rate = audio.sample_rate
        try:
            # audio.get_raw_data() returns bytes in 16-bit little endian PCM
            audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            # fallback: try reading via soundfile (if audio.filename available)
            audio_np = np.array([], dtype=np.float32)
        audio_clean = self.preprocess_audio(audio_np, sample_rate)
        return audio_clean, sample_rate

    # -------------------------
    # Enhanced Liveness detection
    # -------------------------
    def detect_voice_liveness(self, audio_data: np.ndarray, sample_rate: int) -> Tuple[float, List[str]]:
        """
        Enhanced liveness heuristics to detect real human voice vs TTS/deepfake:
         - spectral centroid variance
         - pitch variability (via librosa.piptrack)
         - zero crossing variation
         - energy variation (RMS)
         - spectral rolloff variation
         - MFCC variance
        Returns (score in [0,1], warnings:list)
        Higher score = more likely to be real human voice
        """
        warnings = []
        scores = []
        try:
            y = np.asarray(audio_data, dtype=np.float32)
            # if too short -> neutral score
            if len(y) < int(0.3 * sample_rate):
                return 0.5, ["Audio quá ngắn để kiểm tra liveness"]

            # spectral centroid variance
            try:
                cent = librosa.feature.spectral_centroid(y=y, sr=sample_rate)[0]
                cent_var = float(np.var(cent))
                if cent_var > 50000:
                    scores.append(1.0)
                elif cent_var > 15000:
                    scores.append(0.8)
                else:
                    scores.append(0.4)
                    warnings.append("Phổ tần số khá đều (có thể TTS/deepfake)")
            except Exception:
                scores.append(0.6)

            # pitch variability
            try:
                pitches, mag = librosa.piptrack(y=y, sr=sample_rate)
                pitch_vals = pitches[pitches > 0]
                if len(pitch_vals) > 0:
                    pv = float(np.var(pitch_vals))
                    if pv > 200:
                        scores.append(1.0)
                    elif pv > 50:
                        scores.append(0.75)
                    else:
                        scores.append(0.35)
                        warnings.append("Cao độ ít thay đổi (có thể TTS/deepfake)")
                else:
                    scores.append(0.5)
            except Exception:
                scores.append(0.6)

            # zero crossing rate variance
            try:
                zcr = librosa.feature.zero_crossing_rate(y)[0]
                zcr_var = float(np.var(zcr))
                if zcr_var > 0.01:
                    scores.append(1.0)
                elif zcr_var > 0.005:
                    scores.append(0.8)
                else:
                    scores.append(0.4)
                    warnings.append("ZCR ổn định -> có thể TTS/deepfake")
            except Exception:
                scores.append(0.6)

            # energy (rms) variation
            try:
                rms = librosa.feature.rms(y=y)[0]
                rms_var = float(np.var(rms))
                if rms_var > 0.001:
                    scores.append(1.0)
                elif rms_var > 0.0005:
                    scores.append(0.8)
                else:
                    scores.append(0.45)
            except Exception:
                scores.append(0.6)

            # spectral rolloff variation (additional check)
            try:
                rolloff = librosa.feature.spectral_rolloff(y=y, sr=sample_rate)[0]
                rolloff_var = float(np.var(rolloff))
                if rolloff_var > 100000:
                    scores.append(1.0)
                elif rolloff_var > 50000:
                    scores.append(0.8)
                else:
                    scores.append(0.4)
            except Exception:
                scores.append(0.6)

            # MFCC variance (captures timbral variation)
            try:
                mfccs = librosa.feature.mfcc(y=y, sr=sample_rate, n_mfcc=13)
                mfcc_var = float(np.mean(np.var(mfccs, axis=1)))
                if mfcc_var > 50:
                    scores.append(1.0)
                elif mfcc_var > 20:
                    scores.append(0.75)
                else:
                    scores.append(0.4)
                    warnings.append("MFCC ổn định -> có thể deepfake")
            except Exception:
                scores.append(0.6)

            # Final average
            liveness_score = float(np.mean(scores))
            liveness_score = max(0.0, min(1.0, liveness_score))
            return liveness_score, warnings
        except Exception as e:
            print(f"⚠️ Liveness check error: {e}")
            return 0.5, ["Lỗi khi kiểm tra liveness"]

    # -------------------------
    # Anti-spoofing detection
    # -------------------------
    def detect_voice_spoofing(self, audio_data: np.ndarray, sample_rate: int) -> Tuple[float, bool, List[str]]:
        """
        Advanced anti-spoofing detection to identify deepfake/TTS voices.
        Returns: (spoof_score in [0,1], is_bonafide:bool, warnings:list)
        Higher spoof_score = more likely to be spoofed/deepfake
        """
        warnings = []
        spoof_indicators = []
        
        try:
            y = np.asarray(audio_data, dtype=np.float32)
            if len(y) < int(0.3 * sample_rate):
                return 0.5, True, ["Audio quá ngắn để kiểm tra spoofing"]

            # 1. Check for artificial spectral patterns (TTS artifacts)
            try:
                # Cepstral analysis for detecting TTS artifacts
                cepstrum = librosa.hybrid_cqt(y=y, sr=sample_rate)
                cepstrum_var = float(np.var(np.abs(cepstrum)))
                if cepstrum_var < 0.001:  # Very stable = suspicious
                    spoof_indicators.append(0.8)
                    warnings.append("Cepstrum ổn định -> có thể TTS")
                elif cepstrum_var < 0.005:
                    spoof_indicators.append(0.5)
                else:
                    spoof_indicators.append(0.2)
            except Exception:
                spoof_indicators.append(0.5)

            # 2. Check for unnatural pitch patterns
            try:
                pitches, magnitudes = librosa.piptrack(y=y, sr=sample_rate)
                pitch_values = pitches[pitches > 0]
                if len(pitch_values) > 0:
                    pitch_std = float(np.std(pitch_values))
                    # Real voices have more variation
                    if pitch_std < 20:  # Too stable
                        spoof_indicators.append(0.7)
                        warnings.append("Cao độ quá ổn định -> có thể deepfake")
                    elif pitch_std < 50:
                        spoof_indicators.append(0.4)
                    else:
                        spoof_indicators.append(0.2)
                else:
                    spoof_indicators.append(0.5)
            except Exception:
                spoof_indicators.append(0.5)

            # 3. Check for spectral discontinuities (re-synthesis artifacts)
            try:
                stft = librosa.stft(y)
                magnitude = np.abs(stft)
                # Check for sudden spectral changes (artifacts)
                diff_mag = np.diff(magnitude, axis=1)
                diff_var = float(np.mean(np.var(diff_mag, axis=0)))
                if diff_var > 100:  # High variation = natural
                    spoof_indicators.append(0.2)
                elif diff_var > 50:
                    spoof_indicators.append(0.4)
                else:
                    spoof_indicators.append(0.6)
                    warnings.append("Phổ tần có dấu hiệu tái tạo nhân tạo")
            except Exception:
                spoof_indicators.append(0.5)

            # 4. Check for consistent formant structure (too perfect = suspicious)
            try:
                # Extract formants using autocorrelation
                autocorr = librosa.autocorrelate(y)
                # Real voices have more natural formant variation
                formant_var = float(np.var(autocorr[:int(sample_rate * 0.01)]))
                if formant_var < 0.0001:  # Too consistent
                    spoof_indicators.append(0.7)
                    warnings.append("Cấu trúc formant quá đồng nhất -> có thể deepfake")
                else:
                    spoof_indicators.append(0.3)
            except Exception:
                spoof_indicators.append(0.5)

            # 5. Temporal consistency check
            try:
                # Real speech has natural pauses and variations
                frame_energy = librosa.feature.rms(y=y)[0]
                energy_cv = float(np.std(frame_energy) / (np.mean(frame_energy) + 1e-8))
                if energy_cv < 0.3:  # Too consistent
                    spoof_indicators.append(0.6)
                    warnings.append("Năng lượng âm thanh quá ổn định")
                else:
                    spoof_indicators.append(0.3)
            except Exception:
                spoof_indicators.append(0.5)

            # Calculate final spoof score (weighted average)
            spoof_score = float(np.mean(spoof_indicators))
            is_bonafide = spoof_score < self.spoofing_threshold  # Lower spoof score = more likely bonafide
            
            return spoof_score, is_bonafide, warnings
        except Exception as e:
            print(f"⚠️ Anti-spoofing check error: {e}")
            return 0.5, True, ["Lỗi khi kiểm tra spoofing"]

    # -------------------------
    # ECAPA-TDNN embedding extraction
    # -------------------------
    def extract_ecapa_embedding(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Convert audio to ECAPA-TDNN-compatible waveform (16k, float32) and
        return embedding (numpy array of shape [192] for ECAPA-TDNN).
        """
        try:
            # preprocess and resample
            y = self.preprocess_audio(audio_data, sample_rate)
            y_16k = self.resample_audio(y, sample_rate)
            
            # Ensure minimum length (ECAPA-TDNN needs at least ~0.5s)
            min_length = int(0.5 * self.TARGET_SR)
            if len(y_16k) < min_length:
                # Pad with zeros
                y_16k = np.pad(y_16k, (0, min_length - len(y_16k)), mode='constant')
            
            # Convert to tensor for SpeechBrain
            # ECAPA-TDNN expects shape [batch, samples]
            audio_tensor = torch.FloatTensor(y_16k).unsqueeze(0)
            
            # Move to same device as model (use saved device from __init__)
            audio_tensor = audio_tensor.to(self.device)
            
            # Extract embedding using ECAPA-TDNN
            with torch.no_grad():
                emb = self.speaker_model.encode_batch(audio_tensor)
                # emb is a tensor, convert to numpy
                emb_np = emb.squeeze(0).cpu().numpy()
            
            # ensure numpy array float32
            return np.asarray(emb_np, dtype=np.float32).flatten()
        except Exception as e:
            print(f"❌ Error extracting ECAPA-TDNN embedding: {e}")
            import traceback
            traceback.print_exc()
            # fallback: zeros embedding of size typical for ECAPA-TDNN (192)
            return np.zeros(192, dtype=np.float32)

    # -------------------------
    # Similarity computation
    # -------------------------
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Cosine similarity using ECAPA-TDNN embeddings.
        Returns similarity in [0,1] range (mapped from [-1,1]).
        """
        try:
            a = np.asarray(a, dtype=np.float32)
            b = np.asarray(b, dtype=np.float32)
            if a.size == 0 or b.size == 0:
                return 0.0
            # align dims if needed
            if a.shape != b.shape:
                m = min(a.size, b.size)
                a = a.flatten()[:m]
                b = b.flatten()[:m]
            na = np.linalg.norm(a)
            nb = np.linalg.norm(b)
            if na == 0 or nb == 0:
                return 0.0
            cos = float(np.dot(a, b) / (na * nb))
            # ECAPA-TDNN embeddings are already normalized, similarity is typically in [0.6, 1.0] for same speaker
            # Map from [-1,1] to [0,1] for consistency
            return float((cos + 1.0) / 2.0)
        except Exception as e:
            print(f"⚠️ cosine_similarity error: {e}")
            return 0.0

    def compute_similarity_speechbrain(self, audio1: np.ndarray, audio2: np.ndarray, sr: int) -> float:
        """
        Use SpeechBrain's built-in similarity computation for more accurate results.
        Returns similarity score (typically higher for same speaker with ECAPA-TDNN).
        """
        try:
            # Preprocess both audios
            audio1_clean = self.preprocess_audio(audio1, sr)
            audio2_clean = self.preprocess_audio(audio2, sr)
            
            # Resample
            audio1_16k = self.resample_audio(audio1_clean, sr)
            audio2_16k = self.resample_audio(audio2_clean, sr)
            
            # Ensure minimum length
            min_length = int(0.5 * self.TARGET_SR)
            if len(audio1_16k) < min_length:
                audio1_16k = np.pad(audio1_16k, (0, min_length - len(audio1_16k)), mode='constant')
            if len(audio2_16k) < min_length:
                audio2_16k = np.pad(audio2_16k, (0, min_length - len(audio2_16k)), mode='constant')
            
            # Convert to tensors
            audio1_tensor = torch.FloatTensor(audio1_16k).unsqueeze(0).to(self.device)
            audio2_tensor = torch.FloatTensor(audio2_16k).unsqueeze(0).to(self.device)
            
            # Use SpeechBrain's similarity computation
            with torch.no_grad():
                score, prediction = self.speaker_model.verify_batch(audio1_tensor, audio2_tensor)
                # score is a tensor, extract value
                similarity = float(score.cpu().item())
            
            # SpeechBrain returns probability-like score, map to [0,1]
            return float(similarity)
        except Exception as e:
            print(f"⚠️ SpeechBrain similarity computation error: {e}")
            # Fallback to cosine similarity
            emb1 = self.extract_ecapa_embedding(audio1, sr)
            emb2 = self.extract_ecapa_embedding(audio2, sr)
            return self.cosine_similarity(emb1, emb2)

    # -------------------------
    # Enrollment API
    # -------------------------
    def enroll_voice_biometric(self, user_id: int, num_samples: int = 3) -> bool:
        """
        Record 'num_samples' voice samples (default 3), extract ECAPA-TDNN embeddings
        and save them to DB via EKYCDatabase.save_voice_prints(user_id, features_list, sample_rate)
        """
        print("=== ĐĂNG KÝ GIỌNG NÓI (ECAPA-TDNN - SpeechBrain) ===")
        prompts = ["Tôi yêu Việt Nam", "Sinh trắc học"]
        random_digits = ''.join(str(np.random.randint(0, 10)) for _ in range(6))
        prompts.append(random_digits)

        collected_embeddings = []
        collected_srs = []

        for i, sentence in enumerate(prompts[:num_samples]):
            print(f"\n🗣️ Mẫu {i+1}/{num_samples} — Vui lòng đọc:")
            print(f"   👉 \"{sentence}\"")
            input("   Nhấn Enter khi bạn đã sẵn sàng...")
            audio, sr = self.record_voice_sample(duration=5)
            
            # Enhanced liveness check
            liv_score, liv_warnings = self.detect_voice_liveness(audio, sr)
            if liv_score < self.liveness_threshold:
                print(f"⚠️ Liveness thấp ({liv_score:.2f}). Cảnh báo: {liv_warnings}")
                retry = input("   Thử lại mẫu này? (y/n): ").strip().lower()
                if retry == "y":
                    continue
                else:
                    print("   Tiếp tục lưu mẫu thấp liveness (theo lựa chọn).")
            
            # Anti-spoofing check
            spoof_score, is_bonafide, spoof_warnings = self.detect_voice_spoofing(audio, sr)
            if not is_bonafide:
                print(f"⚠️ Phát hiện dấu hiệu deepfake/spoofing (score: {spoof_score:.2f}). Cảnh báo: {spoof_warnings}")
                retry = input("   Thử lại mẫu này? (y/n): ").strip().lower()
                if retry == "y":
                    continue
                else:
                    print("   ⚠️ Tiếp tục lưu mẫu có dấu hiệu spoofing (theo lựa chọn).")
            
            # Extract ECAPA-TDNN embedding
            emb = self.extract_ecapa_embedding(audio, sr)
            collected_embeddings.append(emb)
            collected_srs.append(sr)
            print(f"   ✅ Đã trích embedding ECAPA-TDNN (len={len(emb)}) — liveness={liv_score:.2f}, spoof_score={spoof_score:.2f}")

        if len(collected_embeddings) < num_samples:
            print("❌ Không đủ mẫu để đăng ký giọng (hủy).")
            return False

        # pick most common sample rate for storage metadata
        most_common_sr = max(set(collected_srs), key=collected_srs.count) if collected_srs else self.TARGET_SR
        # Save to DB
        try:
            self.db.save_voice_prints(user_id, collected_embeddings, most_common_sr)
            print(f"✅ Đã lưu {len(collected_embeddings)} mẫu giọng cho user {user_id}")
            print(f"🔢 Câu ngẫu nhiên đã sử dụng: {random_digits}")
            return True
        except Exception as e:
            print(f"❌ Lỗi lưu vào DB: {e}")
            return False

    # Compatibility wrapper expected by main_ekyc.py
    def enroll_voice(self, user_id: int, num_samples: int = 3):
        return self.enroll_voice_biometric(user_id, num_samples)

    # -------------------------
    # Verification API
    # -------------------------
    def verify_voice_biometric(self, user_id: int) -> Tuple[bool, float, float]:
        """
        OTP-based verification + enhanced liveness + anti-spoofing + ECAPA-TDNN comparison.
        Returns: (success: bool, best_similarity: float in [0,1], liveness_score)
        """
        if not WHISPER_AVAILABLE:
            print("⚠️ Whisper not available — OTP ASR may fail. Install 'whisper' if you want offline ASR.")
        # prepare whisper model if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        whisper_model = None
        if WHISPER_AVAILABLE:
            try:
                whisper_model = whisper.load_model("small", device=device)
            except Exception as e:
                print("⚠️ Failed to load Whisper model:", e)
                whisper_model = None

        # Use saved OTP from DB if available OR generate new OTP verbally
        for attempt in range(3):
            otp_code = ''.join(random.choices("0123456789", k=6))
            digit_to_word = {
                "0": "không", "1": "một", "2": "hai", "3": "ba", "4": "bốn",
                "5": "năm", "6": "sáu", "7": "bảy", "8": "tám", "9": "chín"
            }
            otp_words = ' '.join(digit_to_word[d] for d in otp_code)

            print(f"\n🔐 MÃ XÁC THỰC OTP ({attempt+1}/3): {otp_code}")
            print(f"🗣️ Vui lòng đọc tự nhiên dãy số: {otp_words}")
            input("Nhấn Enter khi sẵn sàng...")

            audio, sr = self.record_voice_sample(duration=8)
            audio = self.preprocess_audio(audio, sr)

            # temporary file for whisper if needed
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                sf.write(tmp_path, audio, sr)

            try:
                transcript = ""
                if whisper_model is not None:
                    print("🎧 Đang nhận dạng bằng Whisper (offline)...")
                    result = whisper_model.transcribe(tmp_path, language="vi")
                    transcript = result.get("text", "").lower().strip()
                else:
                    # fallback: try speech_recognition online (if user has internet)
                    try:
                        r = sr.Recognizer()
                        with sr.AudioFile(tmp_path) as source:
                            audio_sa = r.record(source)
                        transcript = r.recognize_google(audio_sa, language="vi-VN").lower()
                    except Exception as e:
                        print("⚠️ ASR fallback failed:", e)
                        transcript = ""

                # cleanup tmp file
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

                # sanitize transcript -> digits
                transcript_clean = re.sub(r"[^0-9a-zàáãạảăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ\s]", " ", transcript)
                transcript_clean = re.sub(r"\s+", " ", transcript_clean).strip()
                # quick mapping common Vietnamese words to digits
                word_to_digit = {
                    "không": "0", "ko": "0", "kong": "0",
                    "một": "1", "mot": "1", "mốt": "1",
                    "hai": "2",
                    "ba": "3",
                    "bốn": "4", "bon": "4", "tu": "4", "tư": "4",
                    "năm": "5", "nam": "5", "lăm": "5",
                    "sáu": "6", "sau": "6",
                    "bảy": "7", "bay": "7",
                    "tám": "8", "tam": "8",
                    "chín": "9", "chin": "9"
                }
                # extract digits first
                spoken_digits = ''.join(ch for ch in transcript_clean if ch.isdigit())
                if not spoken_digits:
                    words = transcript_clean.split()
                    spoken_digits = ''.join(word_to_digit.get(w, "") for w in words)

                print(f"🗣️ Transcript -> {transcript_clean}")
                print(f"🔢 Chuỗi số sau convert -> {spoken_digits}")

                # simple matching logic
                otp_ok = (spoken_digits == otp_code) or (spoken_digits in otp_code) or (otp_code in spoken_digits)
                if not otp_ok:
                    print("❌ OTP sai — vui lòng nói rõ hơn.")
                    continue

                print("✅ OTP khớp — kiểm tra liveness và anti-spoofing...")
                
                # Enhanced liveness check
                liveness_score, liv_warnings = self.detect_voice_liveness(audio, sr)
                if liveness_score < self.liveness_threshold:
                    print(f"⚠️ Liveness thấp ({liveness_score:.2f}) — từ chối.")
                    if liv_warnings:
                        for w in liv_warnings:
                            print("   -", w)
                    return False, 0.0, liveness_score
                print(f"✅ Liveness OK ({liveness_score:.2f})")
                
                # Anti-spoofing check
                spoof_score, is_bonafide, spoof_warnings = self.detect_voice_spoofing(audio, sr)
                if not is_bonafide:
                    print(f"❌ Phát hiện deepfake/spoofing (score: {spoof_score:.2f}) — từ chối.")
                    if spoof_warnings:
                        for w in spoof_warnings:
                            print("   -", w)
                    return False, 0.0, liveness_score
                print(f"✅ Anti-spoofing OK (spoof_score: {spoof_score:.2f}, bonafide: {is_bonafide})")

                # Extract ECAPA-TDNN embedding for current audio
                current_emb = self.extract_ecapa_embedding(audio, sr)

                # Get stored embeddings
                registered_features_list, stored_sr = self.db.get_voice_prints(user_id)
                if not registered_features_list:
                    print("❌ Không tìm thấy mẫu giọng đã đăng ký.")
                    return False, 0.0, liveness_score

                # Compute similarities using ECAPA-TDNN embeddings
                similarities = []
                for reg in registered_features_list:
                    # reg might be pickled dict or numpy array; ensure numpy
                    reg_arr = np.asarray(reg, dtype=np.float32).flatten()
                    # Use cosine similarity on embeddings
                    sim = self.cosine_similarity(current_emb, reg_arr)
                    similarities.append(sim)

                best_similarity = float(np.max(similarities)) if similarities else 0.0
                avg_similarity = float(np.mean(similarities)) if similarities else 0.0

                print(f"🎯 ECAPA-TDNN Similarity (best): {best_similarity:.4f}, (avg): {avg_similarity:.4f}")
                print(f"📊 Threshold yêu cầu: {self.verification_threshold:.4f}")

                # ECAPA-TDNN thresholding (higher threshold for better security)
                # ECAPA-TDNN typically gives higher scores for same speaker
                if best_similarity >= self.verification_threshold:
                    print("✅ Giọng nói chính chủ — xác thực thành công.")
                    print(f"   🛡️ Đã vượt qua: Liveness + Anti-spoofing + Speaker Verification")
                    return True, best_similarity, liveness_score
                else:
                    print(f"❌ Giọng nói không khớp mẫu đăng ký (threshold: {self.verification_threshold:.4f}, actual: {best_similarity:.4f}).")
                    print(f"   ⚠️ Có thể là người khác đang cố truy cập tài khoản.")
                    return False, best_similarity, liveness_score

            except Exception as e:
                print("⚠️ Lỗi trong quá trình verify:", e)
                import traceback
                traceback.print_exc()
                # try next attempt
                continue

        print("❌ Xác thực thất bại sau 3 lần.")
        return False, 0.0, 0.0

    # Compatibility wrapper expected by main_ekyc.py
    def verify_voice(self, user_id: int) -> Tuple[bool, float, float]:
        return self.verify_voice_biometric(user_id)

    # Alias for backward compatibility
    def cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        return self.cosine_similarity(a, b)
    
    def extract_res_embedding(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Backward compatibility alias"""
        return self.extract_ecapa_embedding(audio_data, sample_rate)
