class Questionnaire {
    constructor() {
        this.initialize().catch(error => {
            console.error('Initialization error:', error);
            this.handleError(error);
        });
    }

    async initialize() {
        try {
            const authResponse = await fetch('/api/auth-check');
            if (authResponse.status === 401) {
                window.location.href = '/google_login';
                return;
            }
            if (!authResponse.ok) {
                throw new Error('Authentication check failed');
            }
            
            // Continue with initialization if authenticated
            const [questionsResponse, answersResponse] = await Promise.all([
                fetch('/api/questions'),
                fetch('/api/saved-answers')
            ]);

            if (!questionsResponse.ok || !answersResponse.ok) {
                throw new Error('Failed to load questionnaire data');
            }

            const [questions, savedAnswers] = await Promise.all([
                questionsResponse.json(),
                answersResponse.json()
            ]);

            this.initializeState(questions, savedAnswers);
            this.setupUI();
            this.updateProgress();

        } catch (error) {
            console.error('Auth check failed:', error);
            window.location.href = '/google_login';
        }
    }

    // ... rest of the class implementation remains unchanged
}

// Initialize questionnaire when document is ready
document.addEventListener('DOMContentLoaded', () => {
    new Questionnaire();
});
