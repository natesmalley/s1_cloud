class Questionnaire {
    constructor() {
        this.questions = [];
        this.currentIndex = 0;
        this.answers = new Map();
        this.validationErrors = new Map();
        this.selectedOptions = new Set();
        this.isLoading = false;
        this.initialize();
    }

    showError(message, isRetryable = true) {
        const container = document.getElementById('questions-container');
        if (container) {
            container.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <div class="d-flex align-items-center">
                        <i data-feather="alert-triangle" class="me-2"></i>
                        <div>
                            ${message}
                            ${isRetryable ? `
                                <button type="button" class="btn btn-link p-0 ms-2" onclick="window.location.reload()">
                                    <i data-feather="refresh-cw" class="me-1"></i>Retry
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
            feather.replace();
        }
    }

    showLoading(message = 'Loading...') {
        const container = document.getElementById('questions-container');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="text-muted">${message}</p>
                </div>
            `;
        }
    }

    async initialize() {
        try {
            this.isLoading = true;
            const container = document.getElementById('questions-container');
            if (!container) {
                throw new Error('Questions container not found');
            }

            this.showLoading('Loading questions...');

            const [questionsResponse, answersResponse] = await Promise.all([
                fetch('/api/questions').catch(error => {
                    throw new Error(`Failed to fetch questions: ${error.message}`);
                }),
                fetch('/api/saved-answers').catch(error => {
                    throw new Error(`Failed to fetch saved answers: ${error.message}`);
                })
            ]);
            
            if (!questionsResponse.ok) {
                throw new Error(`Failed to fetch questions: ${questionsResponse.statusText}`);
            }
            if (!answersResponse.ok) {
                throw new Error(`Failed to fetch answers: ${answersResponse.statusText}`);
            }
            
            const questionsData = await questionsResponse.json();
            const savedAnswers = await answersResponse.json();
            
            if (!questionsData || !Array.isArray(questionsData)) {
                throw new Error('Invalid questions data format');
            }
            
            this.questions = questionsData;
            
            if (savedAnswers && Array.isArray(savedAnswers)) {
                savedAnswers.forEach(answer => {
                    if (answer && answer.question_id) {
                        this.answers.set(answer.question_id, answer.answer);
                        if (Array.isArray(answer.answer)) {
                            answer.answer.forEach(option => this.selectedOptions.add(option));
                        }
                    }
                });
            }
            
            this.renderQuestion();
            this.updateProgress();
            feather.replace();
        } catch (error) {
            console.error('Error loading questionnaire:', error);
            this.showError(error.message || 'Failed to load questionnaire');
        } finally {
            this.isLoading = false;
        }
    }

    renderQuestion() {
        if (this.isLoading) return;

        const container = document.getElementById('questions-container');
        if (!container) return;

        const question = this.questions[this.currentIndex];
        if (!question) {
            this.showError('No question found', false);
            return;
        }

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
                    <div class="validation-feedback mt-3">
                        <div class="selected-count text-muted">
                            ${this.getSelectionCountText(question)}
                        </div>
                        <div id="validation_message" class="mt-2 text-danger">
                            ${this.validationErrors.get(question.id) || ''}
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.addOptionClickHandlers();
    }

    renderQuestionInput(question) {
        if (question.question_type === 'multiple_choice' && Array.isArray(question.options)) {
            return question.options.map(option => `
                <div class="initiative-option">
                    <div class="d-flex align-items-center">
                        <input type="checkbox" class="form-check-input me-2" 
                               id="cb_${option.title.replace(/\s+/g, '_')}"
                               ${this.selectedOptions.has(option.title) ? 'checked' : ''}
                               ${this.selectedOptions.size >= 3 && !this.selectedOptions.has(option.title) ? 'disabled' : ''}>
                        <label class="initiative-title" for="cb_${option.title.replace(/\s+/g, '_')}">
                            ${option.title}
                        </label>
                        <i class="ms-2 text-info" data-feather="help-circle" 
                           data-bs-toggle="tooltip" data-bs-placement="right" 
                           title="${option.description}"></i>
                    </div>
                </div>
            `).join('');
        }
        return '';
    }

    getSelectionCountText(question) {
        const minCount = question.validation_rules?.min_count || 1;
        const maxCount = question.validation_rules?.max_count || 1;
        const currentCount = this.selectedOptions.size;
        
        if (currentCount < minCount) {
            return `Please select at least ${minCount} option${minCount > 1 ? 's' : ''}`;
        } else if (currentCount > maxCount) {
            return `Maximum ${maxCount} option${maxCount > 1 ? 's' : ''} allowed`;
        } else {
            return `Selected ${currentCount} of ${minCount}-${maxCount} required options`;
        }
    }

    async validateCurrentAnswer() {
        const question = this.questions[this.currentIndex];
        if (!question) {
            console.warn('No current question found');
            return false;
        }

        const answer = Array.from(this.selectedOptions);
        
        try {
            const response = await fetch('/api/save-answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question_id: question.id,
                    answer: answer
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to save answer: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            if (result.status === 'success') {
                if (result.is_valid) {
                    this.validationErrors.delete(question.id);
                    this.answers.set(question.id, answer);
                    this.updateProgress(result.progress);
                    return true;
                } else {
                    this.validationErrors.set(question.id, result.message || 'Invalid answer');
                    const feedback = document.getElementById('validation_message');
                    if (feedback) {
                        feedback.textContent = result.message || 'Invalid answer';
                    }
                }
            }
            
            return false;
        } catch (error) {
            console.error('Error validating answer:', error);
            this.showError(error.message || 'Failed to validate answer. Please try again.');
            return false;
        }
    }

    addOptionClickHandlers() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
        const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl)
        });

        feather.replace();

        const checkboxes = document.querySelectorAll('.initiative-option input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', async (event) => {
                const optionTitle = event.target.id.replace('cb_', '').replace(/_/g, ' ');
                if (event.target.checked) {
                    if (this.selectedOptions.size < 3) {
                        this.selectedOptions.add(optionTitle);
                    } else {
                        event.target.checked = false;
                        return;
                    }
                } else {
                    this.selectedOptions.delete(optionTitle);
                }

                checkboxes.forEach(cb => {
                    if (!cb.checked) {
                        cb.disabled = this.selectedOptions.size >= 3;
                    }
                });

                try {
                    await this.validateCurrentAnswer();
                } catch (error) {
                    console.error('Error handling checkbox change:', error);
                    this.showError('Failed to save your selection. Please try again.');
                }
                
                this.renderQuestion();
            });
        });
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
                .catch(error => {
                    console.error('Error updating progress:', error);
                    this.showError('Failed to update progress. Please refresh the page.');
                });
        } else {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
        }
    }

    confirmNavigation() {
        const unsavedChanges = this.selectedOptions.size > 0;
        if (unsavedChanges) {
            return confirm('You have unsaved changes. Are you sure you want to leave?');
        }
        return true;
    }
}

window.addEventListener('beforeunload', (e) => {
    const questionnaire = window.questionnaireInstance;
    if (questionnaire && questionnaire.selectedOptions.size > 0) {
        e.preventDefault();
        e.returnValue = '';
    }
});

document.addEventListener('DOMContentLoaded', () => {
    window.questionnaireInstance = new Questionnaire();
    
    const navigationButtons = document.querySelectorAll('.navigation-buttons button');
    navigationButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            if (!window.questionnaireInstance.confirmNavigation()) {
                e.preventDefault();
            }
        });
    });
});