document.addEventListener('DOMContentLoaded', function() {
    const interviewContainer = document.getElementById('interview-container');
    if (!interviewContainer) return;

    // State management
    const state = {
        sessionId: interviewContainer.dataset.sessionId,
        currentQuestionIndex: 0,
        totalQuestions: 0,
        isRecording: false,
        mediaRecorder: null,
        audioChunks: [],
        timerInterval: null,
        proctoringInterval: null,
        socket: null,
    };

    // UI Elements
    const ui = {
        questionNumber: document.getElementById('question-number'),
        questionText: document.getElementById('current-question-text'),
        chatHistory: document.getElementById('chat-history'),
        statusMessage: document.getElementById('status-message'),
        timer: document.getElementById('timer'),
        recordBtn: document.getElementById('record-btn'),
        repeatBtn: document.getElementById('repeat-btn'),
        skipBtn: document.getElementById('skip-btn'),
        progressDots: document.getElementById('progress-dots'),
        webcamVideo: document.getElementById('webcam-video'),
    };
    
    // --- INITIALIZATION ---
    async function init() {
        console.log(`Initializing interview for session: ${state.sessionId}`);
        
        // Start webcam and proctoring
        await setupWebcamAndProctoring();

        // Fetch the very first question
        fetchQuestion(state.currentQuestionIndex);
    }

    // --- CORE FUNCTIONS ---
    async function fetchQuestion(index) {
        setControlState('loading');
        updateStatus(`Recon AI is preparing question ${index + 1}...`);

        try {
            const response = await fetch(`/get_question/${state.sessionId}/${index}`);
            if (!response.ok) {
                if(response.status === 404) {
                    endInterview();
                    return;
                }
                throw new Error('Failed to fetch question.');
            }
            const data = await response.json();

            // First time setup for total questions
            if(state.totalQuestions === 0) {
                 // We get this from the session storage, or could fetch it
                 const sessionInfo = JSON.parse(localStorage.getItem('interview_session_details'));
                 if (sessionInfo) {
                    state.totalQuestions = parseInt(sessionInfo.total_questions, 10);
                    renderProgressDots();
                 }
            }
            
            displayQuestion(data, index);
            updateProgress(index);

        } catch (error) {
            console.error(error);
            updateStatus("Error loading question. Please refresh.");
        }
    }

    function displayQuestion(data, index) {
        ui.questionNumber.textContent = `Question ${index + 1}`;
        ui.questionText.textContent = data.question;

        addMessageToHistory('ai', data.question);
        
        if (data.audio_url) {
            const audio = new Audio(data.audio_url);
            audio.play();
            audio.onplay = () => setControlState('ai_speaking');
            audio.onended = () => setControlState('user_turn');
        } else {
            setControlState('user_turn');
        }
    }

    function endInterview() {
        updateStatus("Congratulations! You've completed the practice session.");
        setControlState('finished');
        if (state.proctoringInterval) clearInterval(state.proctoringInterval);
        if (state.socket) state.socket.disconnect();
        
        // Redirect to the report page after a delay
        setTimeout(() => {
            alert("Redirecting to your detailed report...");
            // window.location.href = `/report/${state.sessionId}`;
        }, 3000);
    }


    // --- EVENT HANDLERS & UI MANAGEMENT ---
    
    ui.recordBtn.addEventListener('click', () => {
        if (!state.isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    });

    ui.skipBtn.addEventListener('click', () => {
        addMessageToHistory('user', "(Skipped Question)");
        fetchQuestion(++state.currentQuestionIndex);
        // In a real app, we'd also POST to a /skip_question endpoint
    });

    ui.repeatBtn.addEventListener('click', () => {
        fetchQuestion(state.currentQuestionIndex); // Re-fetch the same question
    });
    

    // --- MEDIA & RECORDING ---
    
    async function startRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Your browser does not support audio recording.');
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            state.mediaRecorder = new MediaRecorder(stream);
            state.audioChunks = [];
            
            state.mediaRecorder.ondataavailable = event => {
                state.audioChunks.push(event.data);
            };

            state.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
                stream.getTracks().forEach(track => track.stop());
                await submitAnswer(audioBlob);
            };
            
            state.mediaRecorder.start();
            setControlState('recording');
            startTimer(30);

        } catch(err) {
            alert('Could not access microphone. Please check permissions.');
            console.error(err);
        }
    }

    function stopRecording() {
        if (state.mediaRecorder && state.isRecording) {
            state.mediaRecorder.stop();
            clearInterval(state.timerInterval);
        }
    }

    async function submitAnswer(audioBlob) {
        setControlState('loading');
        updateStatus('Processing your answer...');

        const formData = new FormData();
        formData.append('audio', audioBlob);

        try {
            const response = await fetch(`/submit_answer/${state.sessionId}/${state.currentQuestionIndex}`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Failed to submit answer.');

            const result = await response.json();
            addMessageToHistory('user', result.transcript);
            
            // Move to the next question
            fetchQuestion(++state.currentQuestionIndex);

        } catch (error) {
            console.error(error);
            updateStatus('Error submitting answer. Please try again.');
            setControlState('user_turn');
        }
    }

    // ... (rest of the helper functions: setControlState, updateStatus, addMessageToHistory, timer, proctoring etc.) ...

    init(); // Start the interview process
});

// Helper functions that would be part of the full script
function setControlState(mode) { /* Logic to enable/disable buttons based on mode */ }
function updateStatus(message) { /* Logic to update the status message */ }
function addMessageToHistory(sender, text) { /* Logic to add a bubble to the chat history */ }
function startTimer(duration) { /* Logic for the 30s countdown */ }
function renderProgressDots() { /* Logic to create the progress dots */ }
function updateProgress(index) { /* Logic to update which dot is active */ }
async function setupWebcamAndProctoring() { /* Logic from original script to start webcam and socket.io */ }