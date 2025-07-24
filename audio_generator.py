#!/usr/bin/env python3
"""
Introduction Audio Generator for Recon AI
Run this script to ensure all introduction audios are properly generated
"""

import os
import sys
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason

def generate_tts_file(text, output_path, voice_name="en-US-AriaNeural"):
    """Generate TTS file with proper error handling"""
    try:
        speech_key = os.getenv("AZURE_SPEECH_KEY")
        speech_region = os.getenv("AZURE_SPEECH_REGION")
        
        if not speech_key or not speech_region:
            print("ERROR: Azure Speech credentials not found in environment variables")
            return False
        
        # Configure speech synthesis
        speech_config = SpeechConfig(subscription=speech_key, region=speech_region)
        speech_config.speech_synthesis_voice_name = voice_name
        speech_config.set_speech_synthesis_output_format(1)  # Audio16Khz32KBitRateMonoMp3
        
        # Configure audio output
        audio_config = AudioConfig(filename=output_path)
        
        # Create synthesizer and generate speech
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason == ResultReason.SynthesizingAudioCompleted:
            print(f"✓ Successfully generated: {output_path}")
            return True
        else:
            print(f"✗ Failed to generate: {output_path} (Reason: {result.reason})")
            if result.reason == ResultReason.Canceled:
                print(f"  Error details: {result.cancellation_details.error_details}")
            return False
            
    except Exception as e:
        print(f"✗ Exception generating {output_path}: {str(e)}")
        return False

def main():
    """Main function to generate all introduction audios"""
    
    # Create directories
    os.makedirs("static/audio/introductions", exist_ok=True)
    
    # Recon AI introductions
    recon_introductions = [
        "Welcome to Recon AI — your personal coach for interview success. Think of me as your practice partner, here to boost your confidence, sharpen your skills, and help you shine in every answer. This is your time to take the spotlight.",
        "Hello and welcome to Recon AI. You're not alone in this — I'm here to support you every step of the way. This is your space to practice, grow, and prepare with confidence. Let's begin on a strong note.",
        "Welcome to Recon AI — where preparation meets progress. Whether you're just starting out or polishing your skills, I'm here to help you bring out your best. Let's ease into this experience together.",
        "Hi there, and welcome aboard Recon AI — your smart partner in nailing every interview. Today is about growth, self-belief, and getting one step closer to your goals. You're in the perfect place to begin.",
        "Hey, and welcome to Recon AI — your space to prepare, practice, and gain confidence. No pressure, no rush — just a relaxed environment focused on you and your journey."
    ]
    
    # User introduction prompts
    user_introductions = [
        "To begin, please tell me a little about yourself and what interests you about this opportunity.",
        "Let's start with you introducing yourself. What's your background and what draws you to this field?",
        "I'd love to hear about you first. Could you share your background and what excites you about this role?",
        "Let's kick off with introductions. Tell me about yourself and what motivates you in your career.",
        "To get us started, please introduce yourself and share what passionate you about this industry."
    ]
    
    print("🎤 Generating Recon AI introduction audios...")
    recon_success = 0
    for i, text in enumerate(recon_introductions, 1):
        filepath = f"static/audio/introductions/recon_intro_{i}.mp3"
        if generate_tts_file(text, filepath):
            recon_success += 1
    
    print(f"\n🎤 Generating user introduction audios...")
    user_success = 0
    for i, text in enumerate(user_introductions, 1):
        filepath = f"static/audio/introductions/user_intro_{i}.mp3"
        if generate_tts_file(text, filepath):
            user_success += 1
    
    print(f"\n📊 Generation Summary:")
    print(f"   Recon AI introductions: {recon_success}/5")
    print(f"   User introductions: {user_success}/5")
    print(f"   Total: {recon_success + user_success}/10")
    
    if recon_success + user_success == 10:
        print("\n🎉 All introduction audios generated successfully!")
        return True
    else:
        print("\n⚠️  Some audio files failed to generate. Check your Azure Speech credentials.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)