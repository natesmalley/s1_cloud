class Questionnaire {
    constructor() {
        this.questions = [];
        this.currentIndex = 0;
        this.answers = new Map();
        this.validationErrors = new Map();
        this.selectedOptions = new Set();
        this.initialize();
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
            
            // Initialize answers map with saved answers
            if (Array.isArray(savedAnswers)) {
                savedAnswers.forEach(answer => {
                    this.answers.set(answer.question_id, answer.answer);
                    if (Array.isArray(answer.answer)) {
                        answer.answer.forEach(option => this.selectedOptions.add(option));
                    }
                });
            }
            
            this.renderQuestion();
            this.showControls();
            this.updateProgress();
            feather.replace();
        } catch (error) {
            console.error('Error loading questionnaire:', error);
            this.showError(error.message || 'Failed to load questionnaire. Please refresh the page.');
        }
    }

    renderQuestion() {
        const container = document.getElementById('questions-container');
        if (!container) {
            console.error('Questions container not found');
            return;
        }

        const question = this.questions[this.currentIndex];
        if (!question) return;

        container.innerHTML = `
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title mb-4">
                        ${question.text}
                        ${question.required ? '<span class="text-danger">*</span>' : ''}
                    </h5>
                    <div class="initiatives-container">
                        ${this.renderQuestionInput(question)}
                    </div>
                    <div class="selected-count mt-3">
                        Selected ${this.selectedOptions.size} of ${question.validation_rules?.min_count || 0}-${question.validation_rules?.max_count || 3} required options
                    </div>
                    <div class="invalid-feedback" id="validation-message">
                        ${this.validationErrors.get(question.id) || ''}
                    </div>
                </div>
            </div>
        `;

        this.addOptionClickHandlers();
        feather.replace();
    }

    renderQuestionInput(question) {
        if (question.question_type === 'multiple_choice' && Array.isArray(question.options)) {
            return question.options.map(option => `
                <div class="initiative-option ${this.selectedOptions.has(option.title) ? 'selected' : ''}" 
                     data-option="${option.title}">
                    <div class="initiative-header">
                        <i data-feather="${option.icon}" class="initiative-icon"></i>
                        <h6 class="initiative-title">${option.title}</h6>
                    </div>
                    <p class="initiative-description">${option.description}</p>
                </div>
            `).join('');
        }
        return '';
    }

    addOptionClickHandlers() {
        const options = document.querySelectorAll('.initiative-option');
        options.forEach(option => {
            option.addEventListener('click', () => {
                const optionValue = option.dataset.option;
                const question = this.questions[this.currentIndex];
                const maxCount = question.validation_rules?.max_count || 3;
                const minCount = question.validation_rules?.min_count || 1;

                if (this.selectedOptions.has(optionValue)) {
                    option.classList.remove('selected');
                    this.selectedOptions.delete(optionValue);
                } else if (this.selectedOptions.size < maxCount) {
                    option.classList.add('selected');
                    this.selectedOptions.add(optionValue);
                }

                this.validateCurrentAnswer();
                
                // Update the selected count display
                const countElement = document.querySelector('.selected-count');
                if (countElement) {
                    countElement.textContent = `Selected ${this.selectedOptions.size} of ${minCount}-${maxCount} required options`;
                }
            });
        });
    }

    async validateCurrentAnswer() {
        const question = this.questions[this.currentIndex];
        if (!question) return false;

        const answer = Array.from(this.selectedOptions);
        
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
                throw new Error('Failed to validate answer');
            }
            
            const result = await response.json();
            
            if (result.status === 'success') {
                if (result.is_valid) {
                    this.validationErrors.delete(question.id);
                    this.answers.set(question.id, answer);
                    this.updateProgress(result.progress);
                    return true;
                } else {
                    this.validationErrors.set(question.id, result.message);
                    const feedback = document.getElementById('validation-message');
                    if (feedback) {
                        feedback.style.display = 'block';
                        feedback.textContent = result.message;
                    }
                }
            }
            
            return false;
        } catch (error) {
            console.error('Error validating answer:', error);
            this.showError('Failed to validate answer. Please try again.');
            return false;
        }
    }

    showValidationError(questionId) {
        const message = this.validationErrors.get(questionId);
        const feedback = document.getElementById('validation-message');
        if (feedback) {
            feedback.textContent = message;
            feedback.style.display = 'block';
        }
    }

    showControls() {
        const controls = document.getElementById('navigation-controls');
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const submitBtn = document.getElementById('submit-btn');

        if (!controls || !prevBtn || !nextBtn || !submitBtn) return;

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

    async previousQuestion() {
        if (this.currentIndex > 0) {
            this.selectedOptions.clear();
            const previousAnswer = this.answers.get(this.questions[this.currentIndex - 1].id);
            if (Array.isArray(previousAnswer)) {
                previousAnswer.forEach(option => this.selectedOptions.add(option));
            }
            this.currentIndex--;
            this.renderQuestion();
            this.showControls();
        }
    }

    async nextQuestion() {
        if (await this.validateCurrentAnswer()) {
            this.selectedOptions.clear();
            const nextAnswer = this.answers.get(this.questions[this.currentIndex + 1]?.id);
            if (Array.isArray(nextAnswer)) {
                nextAnswer.forEach(option => this.selectedOptions.add(option));
            }
            this.currentIndex++;
            this.renderQuestion();
            this.showControls();
        }
    }

    updateProgress(progress) {
        const progressBar = document.querySelector('.progress-bar');
        if (!progressBar) return;

        if (progress === undefined) {
            fetch('/api/progress')
                .then(response => response.json())
                .then(data => {
                    if (!data.error) {
                        progressBar.style.width = `${data.progress}%`;
                        progressBar.setAttribute('aria-valuenow', data.progress);
                    }
                })
                .catch(error => console.error('Error updating progress:', error));
        } else {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
        }
    }

    showError(message) {
        const container = document.getElementById('questionnaire-container');
        if (!container) return;

        const existingErrors = container.querySelectorAll('.alert');
        existingErrors.forEach(error => error.remove());

        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show';
        errorDiv.innerHTML = `
            <strong>Error:</strong> ${message}
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
