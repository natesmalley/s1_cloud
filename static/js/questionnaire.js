class Questionnaire {
    constructor() {
        this.questions = [];
        this.currentIndex = 0;
        this.answers = new Map();
        this.initialize();
    }

    async initialize() {
        try {
            const response = await fetch('/api/questions');
            this.questions = await response.json();
            this.renderQuestion();
            this.showControls();
            this.updateProgress();
        } catch (error) {
            console.error('Error loading questions:', error);
        }
    }

    renderQuestion() {
        const container = document.getElementById('questions-container');
        const question = this.questions[this.currentIndex];
        
        container.innerHTML = `
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">${question.text}</h5>
                    ${this.renderQuestionInput(question)}
                </div>
            </div>
        `;
    }

    renderQuestionInput(question) {
        switch (question.type) {
            case 'multiple_choice':
                return question.options.map(option => `
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="answer" value="${option}"
                            ${this.answers.get(question.id) === option ? 'checked' : ''}>
                        <label class="form-check-label">${option}</label>
                    </div>
                `).join('');
            case 'text':
                return `
                    <textarea class="form-control" rows="3">${this.answers.get(question.id) || ''}</textarea>
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

    async saveAnswer() {
        const question = this.questions[this.currentIndex];
        const answer = this.getAnswer();
        
        if (!answer) return false;

        try {
            await fetch('/api/submit-answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question_id: question.id,
                    answer: answer
                })
            });
            this.answers.set(question.id, answer);
            return true;
        } catch (error) {
            console.error('Error saving answer:', error);
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
