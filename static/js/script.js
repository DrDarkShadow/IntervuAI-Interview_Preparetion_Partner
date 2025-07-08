document.addEventListener('DOMContentLoaded', function() {
    // Check which page we're on and initialize accordingly
    if (document.getElementById('skill-form')) {
        initSkillSetupPage();
    } else if (document.querySelector('.company-grid')) {
        initCompanySetupPage();
    }
});

// --- INITIALIZATION FOR SKILL SETUP PAGE ---
function initSkillSetupPage() {
    const form = document.getElementById('skill-form');
    const slider = document.getElementById('skill-questions');
    const sliderValue = document.getElementById('skill-questions-value');
    const topicInput = document.getElementById('topic');
    
    // Setup slider
    if (slider && sliderValue) {
        sliderValue.textContent = slider.value;
        slider.addEventListener('input', () => {
            sliderValue.textContent = slider.value;
        });
    }

    // Setup suggestion tags
    const suggestionTags = document.querySelectorAll('.suggestion-tag');
    if (suggestionTags.length && topicInput) {
        suggestionTags.forEach(tag => {
            tag.addEventListener('click', () => {
                topicInput.value = tag.dataset.topic;
            });
        });
    }
    
    // Handle form submission
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            data.mode = 'topic'; // Add mode for the backend
            startPracticeSession(data);
        });
    }
}

// --- INITIALIZATION FOR COMPANY SETUP PAGE ---
function initCompanySetupPage() {
    const companyCards = document.querySelectorAll('.company-card');
    const detailForm = document.getElementById('company-detail-form');
    const companyNameHiddenInput = document.getElementById('company-name-hidden');
    const formTitle = document.getElementById('company-form-title');
    const slider = document.getElementById('company-questions');
    const sliderValue = document.getElementById('company-questions-value');

    // Setup slider
    if (slider && sliderValue) {
        sliderValue.textContent = slider.value;
        slider.addEventListener('input', () => {
            sliderValue.textContent = slider.value;
        });
    }

    // Handle company card clicks
    companyCards.forEach(card => {
        card.addEventListener('click', () => {
            // Remove 'active' from all cards
            companyCards.forEach(c => c.classList.remove('active'));
            // Add 'active' to the clicked card
            card.classList.add('active');
            
            const companyName = card.dataset.company;
            if (companyName) {
                companyNameHiddenInput.value = companyName;
                formTitle.textContent = `Practice for ${companyName}`;
                detailForm.classList.remove('hidden');
            } else {
                // This is the "Other" card
                // We could show a text input for company name here
                alert('"Other company" functionality will be added in a future version. Please select a company above.');
            }
        });
    });

    // Handle form submission
    if (detailForm) {
        detailForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(detailForm);
            const data = Object.fromEntries(formData.entries());
            data.mode = 'company'; // Add mode for the backend
            startPracticeSession(data);
        });
    }
}

// --- SHARED FUNCTIONALITY ---
function startPracticeSession(configData) {
    console.log('Starting practice session with configuration:', configData);
    
    // Show a loading overlay
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.remove('hidden');
    }
    
    // Simulate backend preparation
    // In a real app, this would be a fetch() call to '/prepare_session'
    setTimeout(() => {
        // Hide loading and show success
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
        }
        
        const successNotification = document.getElementById('success-notification');
        if (successNotification) {
            successNotification.classList.remove('hidden');
        }
        
        // Redirect to the interview page after a short delay
    setTimeout(() => {
            alert('Redirecting to the live interview page...');
            // In a real app:
            // window.location.href = `/interview?session_id=...`;
        }, 1500);

    }, 3000); // Simulate a 3-second preparation time
}