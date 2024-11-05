class Questionnaire {
    constructor() {
        this.questions = [];
        this.currentIndex = 0;
        this.answers = new Map();
        this.validationErrors = new Map();
        this.initialize();
    }

    async initialize() {
        try {
            const [questionsResponse, answersResponse] = await Promise.all([
                fetch('/api/questions'),
                fetch('/api/saved-answers')
            ]);
            
            if (!questionsResponse.ok || !answersResponse.ok) {
                throw new Error('Failed to fetch questionnaire data');
            }
            
            this.questions = await questionsResponse.json();
            const savedAnswers = await answersResponse.json();
            
            if (!Array.isArray(this.questions)) {
                throw new Error('Invalid questions data received');
            }

            if (this.questions.error) {
                throw new Error(this.questions.error);
            }
            
            // Initialize answers map with saved answers
            savedAnswers.forEach(answer => {
                this.answers.set(answer.question_id, answer.answer);
            });
            
            this.renderQuestion();
            this.showControls();
            this.updateProgress();
        } catch (error) {
            console.error('Error loading questionnaire:', error);
            this.showError('Failed to load questionnaire. Please refresh the page.');
        }
    }

    renderQuestion() {
        const container = document.getElementById('questions-container');
        const question = this.questions[this.currentIndex];
        
        if (!question) {
            this.showError('Failed to load question. Please refresh the page.');
            return;
        }

        container.innerHTML = `
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">
                        ${question.text}
                        ${question.required ? '<span class="text-danger">*</span>' : ''}
                    </h5>
                    ${this.renderQuestionInput(question)}
                    <div class="invalid-feedback" id="validation-message">
                        ${this.validationErrors.get(question.id) || 'This field is required'}
                    </div>
                </div>
            </div>
        `;

        // Add event listeners for real-time validation
        if (question.type === 'text') {
            const textarea = container.querySelector('textarea');
            textarea?.addEventListener('input', () => this.validateCurrentAnswer());
        } else {
            const inputs = container.querySelectorAll('input[type="radio"]');
            inputs.forEach(input => {
                input?.addEventListener('change', () => this.validateCurrentAnswer());
            });
        }
    }

    renderQuestionInput(question) {
        const savedAnswer = this.answers.get(question.id);
        const isInvalid = this.validationErrors.has(question.id);
        
        switch (question.type) {
            case 'multiple_choice':
                return question.options.map(option => `
                    <div class="form-check">
                        <input class="form-check-input ${isInvalid ? 'is-invalid' : ''}"
                            type="radio" name="answer" value="${option}"
                            ${savedAnswer === option ? 'checked' : ''}>
                        <label class="form-check-label">${option}</label>
                    </div>
                `).join('');
            case 'text':
                return `
                    <textarea class="form-control ${isInvalid ? 'is-invalid' : ''}"
                        rows="3">${savedAnswer || ''}</textarea>
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

        if (!controls || !prevBtn || !nextBtn || !submitBtn) {
            console.error('Navigation controls not found');
            return;
        }

        controls.classList.remove('d-none');
        prevBtn.disabled = this.currentIndex === 0;
        nextBtn.classList.toggle('d-none', this.currentIndex === this.questions.length - 1);
        submitBtn.classList.toggle('d-none', this.currentIndex !== this.questions.length - 1);

        this.setupEventListeners();
    }

    setupEventListeners() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const submitBtn = document.getElementById('submit-btn');

        if (prevBtn) prevBtn.onclick = () => this.previousQuestion();
        if (nextBtn) nextBtn.onclick = () => this.nextQuestion();
        if (submitBtn) submitBtn.onclick = () => this.submitQuestionnaire();
    }

    async validateCurrentAnswer() {
        const question = this.questions[this.currentIndex];
        const answer = this.getAnswer();
        
        if (!answer && !question.required) {
            this.validationErrors.delete(question.id);
            return true;
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
            
            const result = await response.json();
            
            if (result.status === 'success') {
                if (result.is_valid) {
                    this.validationErrors.delete(question.id);
                    this.answers.set(question.id, answer);
                    this.updateProgress(result.progress);
                    return true;
                } else {
                    this.validationErrors.set(question.id, result.message);
                }
            } else {
                this.validationErrors.set(question.id, result.message);
            }
            
            this.showValidationError(question.id);
            return false;
        } catch (error) {
            console.error('Error validating answer:', error);
            this.showError('Failed to validate answer. Please try again.');
            return false;
        }
    }

    showValidationError(questionId) {
        const container = document.getElementById('questions-container');
        const input = container.querySelector('textarea, input:checked');
        const feedback = container.querySelector('.invalid-feedback');
        
        if (input) {
            input.classList.add('is-invalid');
        }
        if (feedback) {
            feedback.textContent = this.validationErrors.get(questionId);
            feedback.style.display = 'block';
        }
    }

    getAnswer() {
        const question = this.questions[this.currentIndex];
        if (question.type === 'multiple_choice') {
            const selected = document.querySelector('input[name="answer"]:checked');
            return selected ? selected.value : null;
        } else {
            const textarea = document.querySelector('textarea');
            return textarea ? textarea.value.trim() : '';
        }
    }

    async previousQuestion() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.renderQuestion();
            this.showControls();
        }
    }

    async nextQuestion() {
        if (await this.validateCurrentAnswer()) {
            this.currentIndex++;
            this.renderQuestion();
            this.showControls();
        }
    }

    updateProgress(progress) {
        const progressBar = document.querySelector('.progress-bar');
        if (!progressBar) {
            console.error('Progress bar not found');
            return;
        }

        if (progress === undefined) {
            // Fetch progress from server
            fetch('/api/progress')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error fetching progress:', data.error);
                        return;
                    }
                    progressBar.style.width = `${data.progress}%`;
                    progressBar.setAttribute('aria-valuenow', data.progress);
                })
                .catch(error => {
                    console.error('Error updating progress:', error);
                });
        } else {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
        }
    }

    showError(message) {
        const container = document.getElementById('questionnaire-container');
        if (!container) return;

        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show';
        errorDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        container.insertBefore(errorDiv, container.firstChild);
    }

    async submitQuestionnaire() {
        if (await this.validateCurrentAnswer()) {
            try {
                const validateResponse = await fetch('/api/validate-answers');
                if (!validateResponse.ok) {
                    throw new Error('Failed to validate answers');
                }

                const validation = await validateResponse.json();
                
                if (!validation.is_valid) {
                    const messages = validation.invalid_questions
                        .map(q => `Question ${q.question_id}: ${q.message}`)
                        .join('\n');
                    this.showError('Please correct the following errors:\n' + messages);
                    return;
                }
                
                const response = await fetch('/api/generate-roadmap', {
                    method: 'POST'
                });

                if (!response.ok) {
                    throw new Error('Failed to generate roadmap');
                }

                const result = await response.json();
                
                if (result.status === 'success') {
                    window.location.href = `https://docs.google.com/document/d/${result.doc_id}`;
                } else {
                    this.showError(result.message || 'Failed to generate roadmap. Please try again.');
                }
            } catch (error) {
                console.error('Error submitting questionnaire:', error);
                this.showError('An error occurred while generating the roadmap.');
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new Questionnaire();
});
