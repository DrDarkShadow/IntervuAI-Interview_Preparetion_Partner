// --- MODIFIED interview.js ---
document.addEventListener('DOMContentLoaded', function() {
    const interviewContainer = document.getElementById('interview-container');
    if (!interviewContainer) return;

    const state = {
        sessionId: interviewContainer.dataset.sessionId,
        currentQuestionIndex: -1,
        totalQuestions: 0,
        isRecording: false,
        mediaRecorder: null,
        audioChunks: [],
        timerInterval: null,
        userStream: null,
        introductionPhase: 'waiting' // waiting, recon_intro, user_intro, questions
    };

    const ui = {
        questionNumber: document.getElementById('question-number'),
        questionText: document.getElementById('current-question-text'),
        statusMessage: document.getElementById('status-message'),
        timer: document.getElementById('timer'),
        recordBtn: document.getElementById('record-btn'),
        repeatBtn: document.getElementById('repeat-btn'),
        skipBtn: document.getElementById('skip-btn'),
        progressDots: document.getElementById('progress-dots'),
        webcamVideo: document.getElementById('webcam-video'),
        proctoringOverlay: document.getElementById('proctoring-status-overlay')
    };

    const sleep = ms => new Promise(res => setTimeout(res, ms));

    async function init() {
        console.log('[DEBUG] Initializing interview session...');
        setControlState('initializing');
        
        // Get session details from localStorage
        const sessionDetails = JSON.parse(localStorage.getItem('sessionDetails'));
        if (!sessionDetails || sessionDetails.sessionId !== state.sessionId) {
            updateStatus("Error: Session data not found. Redirecting...");
            setTimeout(() => { window.location.href = '/'; }, 2000);
            return;
        }
        
        state.totalQuestions = sessionDetails.totalQuestions;
        renderProgressDots();
        
        // Setup webcam and microphone
        await setupWebcamAndMic();
        
        // Wait for session to be ready
        updateStatus("Preparing your interview session...");
        await waitForSessionReady();
        
        // Start the introduction sequence
        await startIntroductionSequence();
    }

    async function waitForSessionReady() {
        console.log('[DEBUG] Waiting for session to be ready...');
        
        while (true) {
            try {
                const response = await fetch(`/session_status/${state.sessionId}`);
                const status = await response.json();
                
                console.log('[DEBUG] Session status:', status);
                
                if (status.status === 'intro_ready') {
                    console.log('[DEBUG] Session is ready!');
                    return status;
                } else if (status.status === 'error') {
                    throw new Error('Session preparation failed');
                }
                
                // Wait a bit before checking again
                await sleep(1000);
                
            } catch (error) {
                console.error('[ERROR] Failed to check session status:', error);
                updateStatus("Error preparing session. Please refresh the page.");
                return;
            }
        }
    }

    async function startIntroductionSequence() {
        console.log('[DEBUG] Starting introduction sequence...');
        
        try {
            // Get session status to get introduction audios
            const response = await fetch(`/session_status/${state.sessionId}`);
            const sessionData = await response.json();
            
            if (!sessionData.recon_intro_audio || !sessionData.intro_question) {
                throw new Error('Introduction data not available');
            }
            
            // Phase 1: Recon AI Introduction
            state.introductionPhase = 'recon_intro';
            ui.questionNumber.textContent = "Welcome";
            ui.questionText.textContent = "Welcome to Recon AI, your personal interview coach";
            updateStatus("Recon AI is introducing itself...");
            
            console.log('[DEBUG] Playing Recon AI introduction:', sessionData.recon_intro_audio);
            await playAudio(new Audio(sessionData.recon_intro_audio));
            
            // Phase 2: User Introduction Question
            state.introductionPhase = 'user_intro';
            state.currentQuestionIndex = 0; // Introduction is question 0
            
            ui.questionNumber.textContent = "Introduction";
            ui.questionText.textContent = sessionData.intro_question.text;
            updateProgressDots('active');
            
            updateStatus("AI is asking the introduction question...");
            console.log('[DEBUG] Playing user introduction question:', sessionData.intro_question.audio_url);
            await playAudio(new Audio(sessionData.intro_question.audio_url));
            
            // Start recording for user introduction
            state.introductionPhase = 'questions';
            startRecording();
            
        } catch (error) {
            console.error('[ERROR] Failed to start introduction:', error);
            updateStatus("Error starting introduction. Please refresh the page.");
            setControlState('error');
        }
    }

    async function askNextQuestion() {
        console.log('[DEBUG] Asking next question...');
        
        if (state.isRecording) stopRecording();
        if (state.timerInterval) clearInterval(state.timerInterval);

        state.currentQuestionIndex++;
        setControlState('loading');
        
        const isIntro = state.currentQuestionIndex === 0;
        const q_num_display = isIntro ? 'Introduction' : `Question ${state.currentQuestionIndex}`;
        updateStatus(`Loading ${q_num_display.toLowerCase()}...`);

        // Poll for question with timeout and retry logic
        let retryCount = 0;
        const maxRetries = 5;
        
        while (retryCount < maxRetries) {
            try {
                console.log(`[DEBUG] Fetching question ${state.currentQuestionIndex}, attempt ${retryCount + 1}`);
                
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

                const response = await fetch(`/get_question/${state.sessionId}/${state.currentQuestionIndex}`, {
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`Server responded with status ${response.status}`);
                }
                
                const question = await response.json();
                console.log('[DEBUG] Question response:', question);

                // Handle different response types
                if (response.status === 202) {
                    if (question.status === 'generating_questions') {
                        console.log('[DEBUG] Questions still being generated, waiting...');
                        updateStatus("Preparing your questions... Please wait.");
                        await sleep(2000);
                        continue;
                    } else if (question.status === 'not_ready') {
                        console.log('[DEBUG] Question not ready yet, waiting...');
                        await sleep(1000);
                        continue;
                    }
                }
                
                // Check for end of interview
                if (question.end_of_interview) {
                    console.log('[DEBUG] End of interview reached');
                    endInterview();
                    return;
                }
                
                // Check for errors
                if (question.error) {
                    throw new Error(question.error);
                }
                
                // We have a valid question
                console.log('[DEBUG] Question received successfully');
                
                // Update UI
                ui.questionNumber.textContent = `${q_num_display}${isIntro ? '' : ` of ${state.totalQuestions - 1}`}`;
                ui.questionText.textContent = question.text;
                updateProgressDots('active');
                
                // Play question audio
                if (question.audio_url) {
                    updateStatus('AI is asking a question...');
                    await playAudio(new Audio(question.audio_url));
                } else {
                    console.warn('[WARNING] No audio URL for question');
                    updateStatus('Question ready - audio not available');
                    await sleep(1000);
                }
                
                // Start recording
                startRecording();
                return;
                
            } catch (error) {
                retryCount++;
                console.error(`[ERROR] Attempt ${retryCount} failed:`, error);
                
                if (error.name === 'AbortError') {
                    console.warn('[WARNING] Request timed out, retrying...');
                    updateStatus("Request timed out, retrying...");
                } else if (retryCount >= maxRetries) {
                    console.error('[ERROR] Max retries reached');
                    setControlState('error');
                    updateStatus(`Failed to load question after ${maxRetries} attempts. Please refresh the page.`);
                    return;
                } else {
                    console.log(`[DEBUG] Retrying in 2 seconds... (${retryCount}/${maxRetries})`);
                    updateStatus(`Error loading question, retrying... (${retryCount}/${maxRetries})`);
                    await sleep(2000);
                }
            }
        }
    }

    // Event Listeners
    ui.recordBtn.addEventListener('click', () => {
        if (state.isRecording) {
            stopRecording();
        }
    });

    ui.skipBtn.addEventListener('click', () => {
        if (state.currentQuestionIndex >= state.totalQuestions) return;
        
        console.log('[DEBUG] Skipping question');
        updateProgressDots('skipped');
        askNextQuestion();
    });

    ui.repeatBtn.addEventListener('click', async () => {
        if (state.currentQuestionIndex < 0) return;
        
        console.log('[DEBUG] Repeating question');
        
        try {
            const resp = await fetch(`/get_question/${state.sessionId}/${state.currentQuestionIndex}`);
            const question = await resp.json();
            
            if (question.audio_url) {
                updateStatus('Repeating the question...');
                await playAudio(new Audio(question.audio_url));
                startRecording();
            } else {
                updateStatus('Audio not available for this question');
            }
        } catch (error) {
            console.error('[ERROR] Failed to repeat question:', error);
            updateStatus('Error repeating question');
        }
    });

    function startRecording() {
        if (!state.userStream || state.isRecording) {
            console.warn('[WARNING] Cannot start recording - no stream or already recording');
            return;
        }
        
        console.log('[DEBUG] Starting recording...');
        setControlState('recording');
        updateStatus('Recording your answer... Click "Stop" when you are done.');
        
        startTimer(120); // 2 minutes
        state.isRecording = true;
        state.audioChunks = [];
        
        try {
            state.mediaRecorder = new MediaRecorder(state.userStream);
            
            state.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    state.audioChunks.push(event.data);
                }
            };
            
            state.mediaRecorder.onstop = () => {
                console.log('[DEBUG] Recording stopped');
                const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
                state.isRecording = false;
                
                if (audioBlob.size > 1000) { // Minimum size check
                    console.log('[DEBUG] Valid recording, submitting...');
                    setControlState('loading');
                    updateProgressDots('completed');
                    submitAnswer(audioBlob);
                } else {
                    console.log('[DEBUG] Recording too small, treating as skip');
                    updateProgressDots('skipped');
                    askNextQuestion();
                }
            };
            
            state.mediaRecorder.start();
            console.log('[DEBUG] MediaRecorder started');
            
        } catch (error) {
            console.error('[ERROR] Failed to start MediaRecorder:', error);
            state.isRecording = false;
            updateStatus('Error starting recording. Please try again.');
            setControlState('error');
        }
    }

    function stopRecording() {
        if (state.mediaRecorder && state.isRecording) {
            console.log('[DEBUG] Stopping recording...');
            clearInterval(state.timerInterval);
            state.mediaRecorder.stop();
        }
    }

    async function submitAnswer(audioBlob) {
        console.log('[DEBUG] Submitting answer...');
        updateStatus('Processing your answer...');
        
        const formData = new FormData();
        formData.append('audio', audioBlob, 'answer.webm');
        formData.append('question_index', state.currentQuestionIndex);
        
        try {
            const response = await fetch(`/interview_session/${state.sessionId}/submit_answer`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('[DEBUG] Answer submitted successfully:', result);
            
            // Move to next question
            askNextQuestion();
            
        } catch (error) {
            console.error('[ERROR] Failed to submit answer:', error);
            updateStatus('Error submitting answer. Moving to next question...');
            setTimeout(() => askNextQuestion(), 2000);
        }
    }

    async function setupWebcamAndMic() {
        console.log('[DEBUG] Setting up webcam and microphone...');
        
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Your browser does not support media access. Please use a modern browser.');
            setControlState('error');
            return;
        }

        try {
            ui.proctoringOverlay.textContent = 'Requesting camera and microphone permissions...';
            
            state.userStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480 },
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            ui.webcamVideo.srcObject = state.userStream;
            ui.proctoringOverlay.style.display = 'none';
            
            console.log('[DEBUG] Webcam and microphone setup complete');
            
        } catch (error) {
            console.error('[ERROR] Failed to setup media:', error);
            ui.proctoringOverlay.textContent = 'Camera/microphone access denied';
            alert('Please grant camera and microphone permissions and refresh the page.');
            setControlState('error');
        }
    }

    function endInterview() {
        console.log('[DEBUG] Ending interview...');
        setControlState('finished');
        updateStatus("Interview completed! Generating your personalized report...");
        
        // Stop all media streams
        if (state.userStream) {
            state.userStream.getTracks().forEach(track => track.stop());
        }
        
        // Clear any timers
        if (state.timerInterval) {
            clearInterval(state.timerInterval);
        }
        
        // Redirect to report after 3 seconds
        setTimeout(() => {
            window.location.href = `/report/${state.sessionId}`;
        }, 3000);
    }

    function playAudio(audioObject) {
        return new Promise((resolve) => {
            console.log('[DEBUG] Playing audio...');
            setControlState('ai_speaking');
            
            // Mute user microphone during AI speech
            if (state.userStream) {
                state.userStream.getAudioTracks().forEach(track => {
                    track.enabled = false;
                });
            }
            
            audioObject.onended = () => {
                console.log('[DEBUG] Audio playback ended');
                // Re-enable user microphone
                if (state.userStream) {
                    state.userStream.getAudioTracks().forEach(track => {
                        track.enabled = true;
                    });
                }
                resolve();
            };
            
            audioObject.onerror = (error) => {
                console.error('[ERROR] Audio playback error:', error);
                // Re-enable user microphone
                if (state.userStream) {
                    state.userStream.getAudioTracks().forEach(track => {
                        track.enabled = true;
                    });
                }
                resolve();
            };
            
            audioObject.play().catch((error) => {
                console.error('[ERROR] Failed to play audio:', error);
                // Re-enable user microphone
                if (state.userStream) {
                    state.userStream.getAudioTracks().forEach(track => {
                        track.enabled = true;
                    });
                }
                resolve();
            });
        });
    }

    function startTimer(duration) {
        let remaining = duration;
        ui.timer.textContent = formatTime(remaining);
        
        if (state.timerInterval) {
            clearInterval(state.timerInterval);
        }
        
        state.timerInterval = setInterval(() => {
            remaining--;
            ui.timer.textContent = formatTime(remaining);
            
            if (remaining <= 0) {
                clearInterval(state.timerInterval);
                ui.timer.textContent = "Time's Up!";
                if (state.isRecording) {
                    stopRecording();
                }
            }
        }, 1000);
    }

    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    function setControlState(mode) {
        const allButtons = [ui.recordBtn, ui.skipBtn, ui.repeatBtn];
        
        // Reset all buttons
        allButtons.forEach(btn => {
            btn.disabled = true;
            btn.style.display = 'inline-flex';
        });
        
        ui.recordBtn.classList.remove('record-button');
        
        switch (mode) {
            case 'recording':
                ui.skipBtn.disabled = false;
                ui.recordBtn.disabled = false;
                ui.recordBtn.innerHTML = '<i class="fas fa-stop-circle"></i> Stop Recording';
                ui.recordBtn.classList.add('record-button');
                break;
                
            case 'ai_speaking':
                ui.repeatBtn.disabled = false;
                ui.recordBtn.innerHTML = '<i class="fas fa-microphone"></i> Ready to Record';
                break;
                
            case 'loading':
                ui.recordBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                break;
                
            case 'initializing':
                ui.recordBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Initializing...';
                allButtons.forEach(btn => btn.style.display = 'none');
                break;
                
            case 'finished':
                ui.recordBtn.innerHTML = '<i class="fas fa-check"></i> Completed';
                allButtons.forEach(btn => btn.style.display = 'none');
                break;
                
            case 'error':
                ui.recordBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
                allButtons.forEach(btn => btn.style.display = 'none');
                break;
        }
    }

    function updateStatus(message) {
        ui.statusMessage.textContent = message;
        console.log(`[STATUS] ${message}`);
    }

    function renderProgressDots() {
        ui.progressDots.innerHTML = '';
        
        // Introduction dot
        const introDot = document.createElement('span');
        introDot.className = 'progress-dot';
        introDot.title = 'Introduction';
        ui.progressDots.appendChild(introDot);
        
        // Question dots
        for (let i = 1; i < state.totalQuestions; i++) {
            const dot = document.createElement('span');
            dot.className = 'progress-dot';
            dot.title = `Question ${i}`;
            ui.progressDots.appendChild(dot);
        }
    }

    function updateProgressDots(status) {
        const dot = ui.progressDots.children[state.currentQuestionIndex];
        if (!dot) return;
        
        // Remove active class from all dots
        Array.from(ui.progressDots.children).forEach(d => d.classList.remove('active'));
        
        // Update current dot
        dot.classList.remove('completed', 'skipped');
        dot.classList.add(status);
    }

    // Initialize the interview
    init();
});