class Questionnaire {
    constructor() {
        this.questions = [];
        this.currentIndex = 0;
        this.answers = new Map();
        this.validationErrors = new Map();
        this.selectedOptions = new Set();
        this.initialize();
    }

    showError(message) {
        const container = document.getElementById('questions-container');
        if (container) {
            container.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <i data-feather="alert-triangle" class="me-2"></i>
                    ${message}
                </div>
            `;
            feather.replace();
        }
    }

    async initialize() {
        try {
            const container = document.getElementById('questions-container');
            if (!container) {
                console.warn('Questions container not found');
                return;
            }

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
            
            if (!Array.isArray(questionsData)) {
                throw new Error('Invalid questions data format');
            }
            
            if (questionsData.length === 0) {
                container.innerHTML = `
                    <div class="alert alert-info" role="alert">
                        <i data-feather="info" class="me-2"></i>
                        No questions available for this section.
                    </div>
                `;
                feather.replace();
                return;
            }
            
            this.questions = questionsData;
            
            // Initialize answers map with saved answers
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
            this.showControls();
            this.updateProgress();
            feather.replace();
        } catch (error) {
            console.error('Error loading questionnaire:', error);
            const container = document.getElementById('questions-container');
            if (container) {
                container.innerHTML = `
                    <div class="alert alert-danger" role="alert">
                        <i data-feather="alert-triangle" class="me-2"></i>
                        ${error.message || 'Failed to load questionnaire. Please refresh the page.'}
                    </div>
                `;
                feather.replace();
            }
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
                    <div class="selected-count mt-3 text-muted">
                        Selected ${this.selectedOptions.size} of ${question.validation_rules?.min_count || 1}-${question.validation_rules?.max_count || 3} required options
                    </div>
                    <div id="validation_message" class="mt-2 text-danger">
                        ${this.validationErrors.get(question.id) || ''}
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

    async validateCurrentAnswer() {
        const question = this.questions[this.currentIndex];
        if (!question) {
            console.warn('No current question found');
            return false;
        }

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
                throw new Error(`Failed to validate answer: ${response.statusText}`);
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
        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
        const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl)
        });

        // Replace Feather icons
        feather.replace();

        // Add click handlers for checkboxes
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

                // Update disabled state of other checkboxes
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
                
                // Update the selected count display
                const countElement = document.querySelector('.selected-count');
                if (countElement) {
                    const question = this.questions[this.currentIndex];
                    const minCount = question.validation_rules?.min_count || 1;
                    const maxCount = question.validation_rules?.max_count || 3;
                    countElement.textContent = `Selected ${this.selectedOptions.size} of ${minCount}-${maxCount} required options`;
                }
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
}

document.addEventListener('DOMContentLoaded', () => {
    new Questionnaire();
});
