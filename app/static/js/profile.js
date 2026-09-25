// Fonction pour basculer l'affichage des thèmes
function toggleTheme(element) {
    var card = element.closest('.theme-stats-card');
    var body = card.querySelector('.theme-stats-body');
    var indicator = card.querySelector('.expand-indicator');
    
    if (body.style.display === 'none') {
        body.style.display = 'block';
        indicator.style.transform = 'translateY(-50%) rotate(180deg)';
    } else {
        body.style.display = 'none';
        indicator.style.transform = 'translateY(-50%) rotate(0deg)';
    }
}

// Animation au scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -20px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Animer les sections au scroll
document.querySelectorAll('.section').forEach(section => {
    section.style.opacity = '0';
    section.style.transform = 'translateY(20px)';
    section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(section);
});
