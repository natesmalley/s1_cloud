class Questionnaire {
    constructor() {
        this.questions = [];
        this.currentIndex = 0;
        this.answers = new Map();
        this.validationErrors = new Map();
        this.selectedOptions = new Set();
        this.filteredQuestions = [];
        this.initialize();
    }

    initializeFeatherIcons() {
        if (typeof feather !== 'undefined') {
            feather.replace();
        } else {
            console.warn('Feather Icons not loaded, falling back to default icons');
        }
    }

    async initialize() {
        try {
            const [questionsResponse, answersResponse] = await Promise.all([
                fetch('/api/questions'),
                fetch('/api/saved-answers')
            ]);
            
            if (!questionsResponse.ok) {
                throw new Error(`Failed to fetch questions: ${questionsResponse.statusText}`);
            }
            if (!answersResponse.ok) {
                throw new Error(`Failed to fetch answers: ${answersResponse.statusText}`);
            }
            
            const questionsData = await questionsResponse.json();
            const savedAnswers = await answersResponse.json();
            
            if (!Array.isArray(questionsData) || questionsData.length === 0) {
                throw new Error('No questions available');
            }
            
            this.questions = questionsData;
            this.filteredQuestions = [this.questions[0]];  // Start with strategic goals question
            
            // Initialize answers map with saved answers
            if (Array.isArray(savedAnswers)) {
                savedAnswers.forEach(answer => {
                    this.answers.set(answer.question_id, answer.answer);
                    if (Array.isArray(answer.answer)) {
                        answer.answer.forEach(option => this.selectedOptions.add(option));
                    }
                });
                
                // If strategic goals are already selected, update filtered questions
                const strategicGoalsAnswer = savedAnswers.find(a => a.question_id === 1);
                if (strategicGoalsAnswer) {
                    this.updateFilteredQuestions(strategicGoalsAnswer.answer);
                }
            }
            
            this.renderQuestion();
            this.showControls();
            this.updateProgress();
            this.initializeFeatherIcons();
        } catch (error) {
            console.error('Error loading questionnaire:', error);
            this.showError(error.message || 'Failed to load questionnaire. Please refresh the page.');
        }
    }

    // ... rest of the class implementation remains the same ...
}

// Initialize questionnaire after DOM is loaded and feather icons are available
document.addEventListener('DOMContentLoaded', () => {
    // Wait for feather to be loaded
    setTimeout(() => {
        new Questionnaire();
    }, 100);
});
