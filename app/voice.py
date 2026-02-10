import speech_recognition as sr
from pydub import AudioSegment, effects
import io

def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    recognizer = sr.Recognizer()
    
    try:
        print(f"🎧 Processing audio file: {filename} ({len(file_bytes)} bytes)")

        try:
            audio = AudioSegment.from_file(io.BytesIO(file_bytes))
        except Exception as e:
            print(f"❌ Pydub load error: {e}")
            return ""

        print(f"   ⏱ Duration: {len(audio)} ms")
        print(f"   🔊 Volume: {audio.dBFS} dB")

        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)

        audio = effects.normalize(audio)
        print(f"   🔊 Volume after normalize: {audio.dBFS} dB")
        
        wav_io = io.BytesIO()

        audio.export(wav_io, format="wav", codec="pcm_s16le")
        wav_io.seek(0)

        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            
            print("   🌍 Sending to Google STT API...")
            try:
                text = recognizer.recognize_google(audio_data, language="bg-BG")
                print(f"   ✅ Transcribed: '{text}'")
                return text
            except sr.UnknownValueError:
                print("   ❌ Google could not understand the audio (unclear speech).")
                return ""
            except sr.RequestError as e:
                print(f"   ❌ Google API error: {e}")
                return ""
            
    except Exception as e:
        print(f"   ❌ Critical Voice Error: {e}")
        return ""