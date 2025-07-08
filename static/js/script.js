document.addEventListener('DOMContentLoaded', function() {
    // This script now only needs to handle the skill setup page
    initSkillSetupPage();
});

function initSkillSetupPage() {
    const form = document.getElementById('skill-form');
    const skillInput = document.getElementById('skill-input');
    const tagContainer = document.getElementById('tag-container');
    const submitButton = form.querySelector('.submit-button');
    let skills = [];

    // --- Tag Input Logic ---
    function updateTagsUI() {
        // Clear existing tags except for the input
        tagContainer.querySelectorAll('.skill-tag').forEach(tag => tag.remove());
        
        // Add current skills back
        for (const skill of skills) {
            const tagElement = document.createElement('div');
            tagElement.classList.add('skill-tag');
            tagElement.textContent = skill;
            
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button'; // Prevent form submission
            removeBtn.classList.add('tag-remove-btn');
            removeBtn.innerHTML = '×';
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Stop click from propagating to the container
                skills = skills.filter(s => s !== skill);
                updateTagsUI();
            });
            
            tagElement.appendChild(removeBtn);
            tagContainer.insertBefore(tagElement, skillInput);
        }
        // Enable/disable submit button based on whether there are any skills
        submitButton.disabled = skills.length === 0;
    }

    skillInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const skill = skillInput.value.trim();
            if (skill && !skills.includes(skill)) {
                skills.push(skill);
                skillInput.value = '';
                updateTagsUI();
            }
        }
    });

    // --- Form Submission ---
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        data.skills = skills; // Add our skills array to the form data
        startPracticeSession(data);
    });

    // --- Sliders and Level Cards ---
    const slider = document.getElementById('skill-questions');
    const sliderValue = document.getElementById('skill-questions-value');
    if (slider && sliderValue) {
        sliderValue.textContent = slider.value;
        slider.addEventListener('input', () => sliderValue.textContent = slider.value);
    }

    document.querySelectorAll('.level-option').forEach(option => {
        option.addEventListener('click', function() {
            document.querySelectorAll('.level-option .level-card').forEach(card => card.classList.remove('active'));
            this.querySelector('.level-card').classList.add('active');
        });
        // Set initial active state for checked radio
        if (option.querySelector('input').checked) {
             option.querySelector('.level-card').classList.add('active');
        }
    });
}

async function startPracticeSession(configData) {
    const loadingOverlay = document.getElementById('loading-overlay');
    if(loadingOverlay) loadingOverlay.classList.remove('hidden');

    console.log('Starting practice session with configuration:', configData);

    try {
        const response = await fetch('/prepare_session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to prepare session.');
        }

        const result = await response.json();
        console.log('Session prepared:', result);

        if(loadingOverlay) loadingOverlay.classList.add('hidden');
        
        alert(`V2 COMPLETE:\nSession created with ID: ${result.session_id}\n\nNext step is to build the page that uses this data.\nFirst Question: "${result.first_question.text}"\nAudio URL: ${result.first_question.audio_url}`);
        
        // In a real app, we would redirect:
        // window.location.href = `/interview/${result.session_id}`;

    } catch (error) {
        console.error('Error starting session:', error);
        if(loadingOverlay) loadingOverlay.classList.add('hidden');
        alert(`Error: ${error.message}`);
    }
}