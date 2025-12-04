"""
Quick test script to verify all components
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from friday.config import Config
from friday.utils.logger import get_logger

logger = get_logger("test")


def test_configuration():
    """Test configuration loading"""
    print("=" * 50)
    print("Testing Configuration...")
    print("=" * 50)

    errors = Config.validate()
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"   - {error}")
        return False
    else:
        print("✅ Configuration valid")
        print(f"   OpenAI API Key: {Config.OPENAI_API_KEY[:20]}...")
        print(f"   Porcupine Key: {Config.PORCUPINE_ACCESS_KEY[:20]}...")
        print(f"   Wake Word: {Config.WAKE_WORD}")
        return True


def test_imports():
    """Test all module imports"""
    print("\n" + "=" * 50)
    print("Testing Imports...")
    print("=" * 50)

    modules = [
        ("GUI", "friday.gui.main_window"),
        ("Conversation", "friday.models.conversation"),
        ("OpenAI Client", "friday.ai.openai_client"),
        ("TTS", "friday.ai.text_to_speech"),
        ("STT", "friday.ai.speech_to_text"),
        ("Vision", "friday.ai.vision_handler"),
        ("Audio Recorder", "friday.audio.audio_recorder"),
        ("Wake Word", "friday.audio.wake_word_detector"),
        ("Screenshot", "friday.utils.screenshot"),
    ]

    all_ok = True
    for name, module in modules:
        try:
            __import__(module)
            print(f"✅ {name}")
        except Exception as e:
            print(f"❌ {name}: {e}")
            all_ok = False

    return all_ok


def test_microphone():
    """Test microphone access"""
    print("\n" + "=" * 50)
    print("Testing Microphone...")
    print("=" * 50)

    try:
        from friday.audio.audio_recorder import AudioRecorder
        recorder = AudioRecorder()

        if recorder.test_microphone():
            print("✅ Microphone accessible")
            return True
        else:
            print("❌ Microphone test failed")
            return False

    except Exception as e:
        print(f"❌ Microphone error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("FRIDAY AI ASSISTANT - SYSTEM CHECK")
    print("=" * 60)

    results = []

    # Test configuration
    results.append(("Configuration", test_configuration()))

    # Test imports
    results.append(("Module Imports", test_imports()))

    # Test microphone
    results.append(("Microphone", test_microphone()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)

    if all_passed:
        print("🎉 ALL SYSTEMS GO! Ready to run Friday.")
        print("\nRun the application with:")
        print("   python run.py")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("   - Check your .env file has both API keys")
        print("   - Install dependencies: pip install -r requirements.txt")
        print("   - Check microphone permissions in Windows Settings")

    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
