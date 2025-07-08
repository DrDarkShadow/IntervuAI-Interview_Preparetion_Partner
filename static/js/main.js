// --- START OF MODIFIED main.js ---
document.addEventListener('DOMContentLoaded', function() {

    // Create floating particles for the background
    function createParticles() {
        const particlesContainer = document.getElementById('particles');
        if (!particlesContainer) return;
        
        const particleCount = 15;
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.left = Math.random() * 100 + '%';
            particle.style.animationDelay = Math.random() * 15 + 's';
            particle.style.animationDuration = (Math.random() * 10 + 10) + 's';
            particlesContainer.appendChild(particle);
        }
    }

    // Header scroll effect
    window.addEventListener('scroll', () => {
        const header = document.querySelector('.app-header');
        if (!header) return;
        
        if (window.scrollY > 50) { // Changed threshold for a quicker effect
            header.style.background = 'rgba(255, 255, 255, 0.98)';
            header.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.05)';
        } else {
            header.style.background = 'rgba(255, 255, 255, 0.95)';
            header.style.boxShadow = 'none';
        }
    });

    // Staggered animations for cards on load
    const cards = document.querySelectorAll('.practice-card');
    cards.forEach((card, index) => {
        card.style.animation = `fadeInUp 1s ease-out ${0.4 + index * 0.2}s both`;
    });

    // Initialize particles
    createParticles();
});
// --- END OF MODIFIED main.js ---