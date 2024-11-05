class Questionnaire {
    constructor() {
        this.questions = [];
        this.currentIndex = 0;
        this.answers = new Map();
        this.initialize();
    }

    async initialize() {
        try {
            // Load questions and saved answers
            const [questionsResponse, answersResponse] = await Promise.all([
                fetch('/api/questions'),
                fetch('/api/saved-answers')
            ]);
            
            this.questions = await questionsResponse.json();
            const savedAnswers = await answersResponse.json();
            
            // Initialize answers map with saved answers
            savedAnswers.forEach(answer => {
                this.answers.set(answer.question_id, answer.answer);
            });
            
            this.renderQuestion();
            this.showControls();
            this.updateProgress();
        } catch (error) {
            console.error('Error loading questionnaire:', error);
        }
    }

    renderQuestion() {
        const container = document.getElementById('questions-container');
        const question = this.questions[this.currentIndex];
        
        container.innerHTML = `
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">${question.text} <span class="text-danger">*</span></h5>
                    ${this.renderQuestionInput(question)}
                    <div class="invalid-feedback" id="validation-message">
                        This field is required
                    </div>
                </div>
            </div>
        `;

        // Add event listeners for real-time validation
        if (question.type === 'text') {
            const textarea = container.querySelector('textarea');
            textarea.addEventListener('input', () => this.validateCurrentAnswer());
        } else {
            const inputs = container.querySelectorAll('input[type="radio"]');
            inputs.forEach(input => {
                input.addEventListener('change', () => this.validateCurrentAnswer());
            });
        }
    }

    renderQuestionInput(question) {
        const savedAnswer = this.answers.get(question.id);
        
        switch (question.type) {
            case 'multiple_choice':
                return question.options.map(option => `
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="answer" value="${option}"
                            ${savedAnswer === option ? 'checked' : ''}>
                        <label class="form-check-label">${option}</label>
                    </div>
                `).join('');
            case 'text':
                return `
                    <textarea class="form-control" rows="3">${savedAnswer || ''}</textarea>
                `;
            default:
                return '<p class="text-danger">Unsupported question type</p>';
        }
    }

    showControls() {
        const controls = document.getElementById('navigation-controls');
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const submitBtn = document.getElementById('submit-btn');

        controls.classList.remove('d-none');
        prevBtn.disabled = this.currentIndex === 0;
        nextBtn.classList.toggle('d-none', this.currentIndex === this.questions.length - 1);
        submitBtn.classList.toggle('d-none', this.currentIndex !== this.questions.length - 1);

        this.setupEventListeners();
    }

    setupEventListeners() {
        document.getElementById('prev-btn').onclick = () => this.previousQuestion();
        document.getElementById('next-btn').onclick = () => this.nextQuestion();
        document.getElementById('submit-btn').onclick = () => this.submitQuestionnaire();
    }

    validateCurrentAnswer() {
        const answer = this.getAnswer();
        const isValid = answer && answer.trim() !== '';
        
        const container = document.getElementById('questions-container');
        const input = container.querySelector('textarea, input:checked');
        const feedback = container.querySelector('.invalid-feedback');
        
        if (input) {
            input.classList.toggle('is-invalid', !isValid);
        }
        if (feedback) {
            feedback.style.display = isValid ? 'none' : 'block';
        }
        
        return isValid;
    }

    async saveAnswer() {
        const question = this.questions[this.currentIndex];
        const answer = this.getAnswer();
        
        if (!this.validateCurrentAnswer()) {
            return false;
        }

        try {
            const response = await fetch('/api/submit-answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question_id: question.id,
                    answer: answer
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to save answer');
            }
            
            this.answers.set(question.id, answer);
            return true;
        } catch (error) {
            console.error('Error saving answer:', error);
            alert('Failed to save your answer. Please try again.');
            return false;
        }
    }

    getAnswer() {
        const question = this.questions[this.currentIndex];
        if (question.type === 'multiple_choice') {
            const selected = document.querySelector('input[name="answer"]:checked');
            return selected ? selected.value : null;
        } else {
            const textarea = document.querySelector('textarea');
            return textarea.value.trim();
        }
    }

    async previousQuestion() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.renderQuestion();
            this.showControls();
            this.updateProgress();
        }
    }

    async nextQuestion() {
        if (await this.saveAnswer()) {
            this.currentIndex++;
            this.renderQuestion();
            this.showControls();
            this.updateProgress();
        }
    }

    updateProgress() {
        const progressBar = document.querySelector('.progress-bar');
        const progress = ((this.currentIndex + 1) / this.questions.length) * 100;
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
    }

    async submitQuestionnaire() {
        if (await this.saveAnswer()) {
            try {
                const response = await fetch('/api/generate-roadmap', {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.status === 'success') {
                    window.location.href = `https://docs.google.com/document/d/${result.doc_id}`;
                } else {
                    alert('Failed to generate roadmap. Please try again.');
                }
            } catch (error) {
                console.error('Error generating roadmap:', error);
                alert('An error occurred while generating the roadmap.');
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new Questionnaire();
});
