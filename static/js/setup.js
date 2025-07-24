// --- START OF UPDATED FILE static/js/setup.js ---

document.addEventListener('DOMContentLoaded', function () {
    // Determine which setup page we are on and initialize it.
    if (document.getElementById('skill-form')) {
        initSkillSetupPage();
    }
    if (document.getElementById('company-detail-form')) {
        initCompanySetupPage();
    }
});

/**
 * Initializes the logic for the "Practice by Skill" page.
 */
function initSkillSetupPage() {
    const form = document.getElementById('skill-form');
    const skillInput = document.getElementById('skill-input');
    const tagContainer = document.getElementById('tag-container');
    const submitButton = form.querySelector('.submit-button');
    const slider = document.getElementById('skill-questions');
    const sliderValue = document.getElementById('skill-questions-value');
    let skills = [];

    const urlParams = new URLSearchParams(window.location.search);
    const skillFromURL = urlParams.get('skill');

    if (skillFromURL) {
        skills.push(skillFromURL);
        updateTagsUI();
    }

    function updateTagsUI() {
        // Clear existing tags
        tagContainer.querySelectorAll('.skill-tag').forEach(tag => tag.remove());

        for (const skill of skills) {
            const tagElement = document.createElement('div');
            tagElement.classList.add('skill-tag');
            tagElement.textContent = skill;

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.classList.add('tag-remove-btn');
            removeBtn.innerHTML = '×';

            removeBtn.addEventListener('click', () => {
                skills = skills.filter(s => s !== skill);
                updateTagsUI();
            });

            tagElement.appendChild(removeBtn);
            tagContainer.insertBefore(tagElement, skillInput);
        }

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

    if (slider && sliderValue) {
        sliderValue.textContent = slider.value;
        slider.addEventListener('input', () => {
            sliderValue.textContent = slider.value;
        });
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const configData = Object.fromEntries(formData.entries());
        configData.skills = skills;
        startPracticeSession(configData);
    });
}

/**
 * Initializes the logic for the "Prepare for a Company" page.
 */
function initCompanySetupPage() {
    const form = document.getElementById('company-detail-form');
    const companyCards = document.querySelectorAll('.company-card');
    const hiddenCompanyInput = document.getElementById('company-name-hidden');
    const formTitle = document.getElementById('company-form-title');
    const slider = document.getElementById('company-questions');
    const sliderValue = document.getElementById('company-questions-value');

    companyCards.forEach(card => {
        card.addEventListener('click', () => {
            const companyName = card.dataset.company;

            // "Other" card logic (placeholder for now)
            if (!companyName) {
                alert("Adding a custom company will be supported soon. Please select an available company.");
                return;
            }

            companyCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');

            hiddenCompanyInput.value = companyName;
            formTitle.textContent = `Details for ${companyName}`;
            form.classList.remove('hidden');
            form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });

    if (slider && sliderValue) {
        sliderValue.textContent = slider.value;
        slider.addEventListener('input', () => {
            sliderValue.textContent = slider.value;
        });
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const configData = Object.fromEntries(formData.entries());
        startPracticeSession(configData);
    });
}

/**
 * Starts a practice session by calling the backend with configuration data.
 */
async function startPracticeSession(configData) {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) loadingOverlay.classList.remove('hidden');

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

        localStorage.setItem('sessionDetails', JSON.stringify({
            sessionId: result.session_id,
            totalQuestions: parseInt(result.num_questions, 10)
        }));

        window.location.href = `/interview/${result.session_id}`;
    } catch (error) {
        console.error('Error starting session:', error);
        if (loadingOverlay) loadingOverlay.classList.add('hidden');
        alert(`Error: ${error.message}`);
    }
}
// --- END OF UPDATED FILE static/js/setup.js ---
