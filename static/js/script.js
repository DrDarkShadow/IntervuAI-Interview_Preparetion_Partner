document.addEventListener('DOMContentLoaded', function() {
    // This script will handle the logic for the setup page
    const topicForm = document.getElementById('topic-form');
    const companyForm = document.getElementById('company-form');
    const setupTitle = document.getElementById('setup-title');
    const setupDescription = document.getElementById('setup-description');

    // Check if we are on the setup page
    if (topicForm && companyForm && setupTitle && setupDescription) {
        const urlParams = new URLSearchParams(window.location.search);
        const mode = urlParams.get('mode');

        if (mode === 'topic') {
            setupTitle.textContent = 'Practice by Skill';
            setupDescription.textContent = 'Let\'s focus on a specific area. Fill out the details below to begin your practice session.';
            topicForm.classList.remove('hidden');
        } else if (mode === 'company') {
            setupTitle.textContent = 'Prepare for a Company';
            setupDescription.textContent = 'Get tailored questions for a specific company and role. Fill out the details to start.';
            companyForm.classList.remove('hidden');
        } else {
            setupTitle.textContent = 'Invalid Setup';
            setupDescription.innerHTML = 'Something went wrong. Please <a href="/" style="color: var(--primary-color);">return to the homepage</a> and select a practice mode.';
        }
        
        // Add event listeners for form submission
        topicForm.addEventListener('submit', handleFormSubmit);
        companyForm.addEventListener('submit', handleFormSubmit);
    }
});

/**
 * NEW: Upgraded form submission handler
 * This function now shows a professional loading overlay, simulates
 * an async operation (like calling an AI backend), and then provides
 * feedback to the user.
 */
function handleFormSubmit(event) {
    event.preventDefault(); // Prevent the default form submission
    
    // 1. Get the loading overlay and the form data
    const loadingOverlay = document.getElementById('loading-overlay');
    const form = event.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    console.log('Starting practice session with the following configuration:');
    console.log(data);
    
    // 2. Show the full-page loading animation
    if(loadingOverlay) {
        loadingOverlay.classList.remove('hidden');
    }
    
    // 3. Simulate an API call to the backend.
    // In a real application, you would use fetch() here to send `data`
    // to your server and wait for a response.
    setTimeout(() => {
        // 4. On "success" from the backend...

        // For now, we'll just show an alert. In a real app, you would
        // redirect to the actual interview page.
        alert('Your AI-powered interview session is ready! The interview would start now. (This is a placeholder for V1)');

        // Example of redirecting:
        // window.location.href = '/interview?session_id=' + someSessionId;

        // 5. Hide the loading animation
        if(loadingOverlay) {
            loadingOverlay.classList.add('hidden');
        }
        
    }, 3500); // Simulate a 3.5-second processing time
}