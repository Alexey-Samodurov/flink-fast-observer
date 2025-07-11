/**
 * Dashboard JavaScript для Flink Observer
 */

// Глобальные переменные
let refreshInterval;
let isRefreshing = false;

// Утилиты
const Utils = {
    // Форматирование времени
    formatDateTime(dateString) {
        return new Date(dateString).toLocaleString('ru-RU');
    },

    // Форматирование длительности
    formatDuration(milliseconds) {
        if (!milliseconds) return '-';

        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}д ${hours % 24}ч`;
        if (hours > 0) return `${hours}ч ${minutes % 60}м`;
        if (minutes > 0) return `${minutes}м ${seconds % 60}с`;
        return `${seconds}с`;
    },

    // Показать уведомление
    showNotification(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        // Автоматическое скрытие через 5 секунд
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    },

    // Получение CSS класса для состояния джоба
    getStateBadgeClass(state) {
        const stateClasses = {
            'RUNNING': 'bg-success',
            'FAILED': 'bg-danger',
            'FINISHED': 'bg-secondary',
            'CANCELED': 'bg-warning',
            'CANCELING': 'bg-warning',
            'SUSPENDED': 'bg-info',
            'RESTARTING': 'bg-primary'
        };
        return stateClasses[state] || 'bg-secondary';
    },

    // Получение иконки для состояния
    getStateIcon(state) {
        const stateIcons = {
            'RUNNING': 'fas fa-play-circle',
            'FAILED': 'fas fa-times-circle',
            'FINISHED': 'fas fa-check-circle',
            'CANCELED': 'fas fa-stop-circle',
            'CANCELING': 'fas fa-pause-circle',
            'SUSPENDED': 'fas fa-pause-circle',
            'RESTARTING': 'fas fa-redo-alt'
        };
        return stateIcons[state] || 'fas fa-question-circle';
    }
};

// API функции
const API = {
    async fetchAPI(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Получить статистику
    async getStatistics() {
        return Promise.all([
            this.fetchAPI('/api/jobs/statistics'),
            this.fetchAPI('/api/clusters?active_only=true')
        ]);
    },

    // Получить кластеры
    async getClusters() {
        return this.fetchAPI('/api/clusters');
    },

    // Получить джобы
    async getJobs(limit = 50) {
        return this.fetchAPI(`/api/jobs?limit=${limit}`);
    },

    // Создать кластер
    async createCluster(clusterData) {
        return this.fetchAPI('/api/clusters', {
            method: 'POST',
            body: JSON.stringify(clusterData)
        });
    },

    // Обновить кластер
    async updateCluster(clusterId, clusterData) {
        return this.fetchAPI(`/api/clusters/${clusterId}`, {
            method: 'PUT',
            body: JSON.stringify(clusterData)
        });
    },

    // Удалить кластер
    async deleteCluster(clusterId) {
        return this.fetchAPI(`/api/clusters/${clusterId}`, {
            method: 'DELETE'
        });
    },

    // Активировать/деактивировать кластер
    async toggleCluster(clusterId, action) {
        return this.fetchAPI(`/api/clusters/${clusterId}/${action}`, {
            method: 'POST'
        });
    },

    // Запустить сбор данных
    async collectData() {
        return this.fetchAPI('/api/collect', {
            method: 'POST'
        });
    },

    // Проверить здоровье системы
    async healthCheck() {
        return this.fetchAPI('/api/health');
    }
};

// Компоненты UI
const UI = {
    // Загрузка статистики
    async loadStats() {
        try {
            const [stats, clusters] = await API.getStatistics();

            document.getElementById('total-clusters').textContent = clusters.length;
            document.getElementById('running-jobs').textContent = stats.states.RUNNING || 0;
            document.getElementById('failed-jobs').textContent = stats.states.FAILED || 0;
            document.getElementById('total-jobs').textContent = stats.total_jobs || 0;
        } catch (error) {
            console.error('Error loading stats:', error);
            Utils.showNotification('Ошибка загрузки статистики', 'danger');
        }
    },

    // Загрузка кластеров
    async loadClusters() {
        try {
            const clusters = await API.getClusters();
            const container = document.getElementById('clusters-container');

            if (clusters.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted">
                        <i class="fas fa-server fa-3x mb-3"></i>
                        <p>Нет добавленных кластеров</p>
                        <button class="btn btn-primary" onclick="Modal.showAddCluster()">
                            <i class="fas fa-plus"></i> Добавить первый кластер
                        </button>
                    </div>
                `;
                return;
            }

            container.innerHTML = clusters.map(cluster => `
                <div class="card cluster-card mb-3 fade-in">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="card-title mb-2">
                                    <i class="fas fa-server me-2"></i>
                                    ${cluster.name}
                                    <span class="badge ${cluster.is_active ? 'bg-success' : 'bg-secondary'} ms-2">
                                        ${cluster.is_active ? 'Активный' : 'Неактивный'}
                                    </span>
                                </h6>
                                <p class="card-text cluster-url mb-1">${cluster.url}</p>
                                ${cluster.description ? `<p class="card-text text-muted mb-0">${cluster.description}</p>` : ''}
                                <small class="text-muted">
                                    <i class="fas fa-clock me-1"></i>
                                    Создан: ${Utils.formatDateTime(cluster.created_at)}
                                </small>
                            </div>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" 
                                        data-bs-toggle="dropdown" aria-expanded="false">
                                    <i class="fas fa-ellipsis-v"></i>
                                </button>
                                <ul class="dropdown-menu">
                                    <li>
                                        <a class="dropdown-item" href="#" 
                                           onclick="Actions.toggleCluster(${cluster.id}, ${cluster.is_active})">
                                            <i class="fas fa-power-off me-2"></i>
                                            ${cluster.is_active ? 'Деактивировать' : 'Активировать'}
                                        </a>
                                    </li>
                                    <li>
                                        <a class="dropdown-item" href="#" 
                                           onclick="Modal.showEditCluster(${JSON.stringify(cluster).replace(/"/g, '&quot;')})">
                                            <i class="fas fa-edit me-2"></i>
                                            Редактировать
                                        </a>
                                    </li>
                                    <li><hr class="dropdown-divider"></li>
                                    <li>
                                        <a class="dropdown-item text-danger" href="#" 
                                           onclick="Actions.deleteCluster(${cluster.id}, '${cluster.name}')">
                                            <i class="fas fa-trash me-2"></i>
                                            Удалить
                                        </a>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading clusters:', error);
            document.getElementById('clusters-container').innerHTML =
                '<div class="alert alert-danger">Ошибка загрузки кластеров</div>';
        }
    },

    // Загрузка джобов
    async loadJobs() {
        try {
            const jobs = await API.getJobs();
            const container = document.getElementById('jobs-container');

            if (jobs.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted">
                        <i class="fas fa-tasks fa-3x mb-3"></i>
                        <p>Нет данных о джобах</p>
                        <button class="btn btn-outline-primary" onclick="Actions.collectData()">
                            <i class="fas fa-sync-alt me-2"></i>
                            Запустить сбор данных
                        </button>
                    </div>
                `;
                return;
            }

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead class="table-light">
                            <tr>
                                <th><i class="fas fa-server me-1"></i>Кластер</th>
                                <th><i class="fas fa-tasks me-1"></i>Джоб</th>
                                <th><i class="fas fa-info-circle me-1"></i>Состояние</th>
                                <th><i class="fas fa-tag me-1"></i>Тип</th>
                                <th><i class="fas fa-clock me-1"></i>Длительность</th>
                                <th><i class="fas fa-calendar me-1"></i>Обновлено</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${jobs.map(job => `
                                <tr class="fade-in">
                                    <td>
                                        <span class="badge bg-info">${job.cluster_name}</span>
                                    </td>
                                    <td>
                                        <div class="text-truncate" style="max-width: 200px;" title="${job.job_name || job.job_id}">
                                            ${job.job_name || job.job_id}
                                        </div>
                                    </td>
                                    <td>
                                        <span class="badge ${Utils.getStateBadgeClass(job.job_state)}">
                                            <i class="${Utils.getStateIcon(job.job_state)} me-1"></i>
                                            ${job.job_state}
                                        </span>
                                    </td>
                                    <td>
                                        <span class="badge bg-light text-dark">${job.job_type || 'N/A'}</span>
                                    </td>
                                    <td>
                                        <span class="job-duration">${Utils.formatDuration(job.job_duration)}</span>
                                    </td>
                                    <td>
                                        <small class="text-muted">${Utils.formatDateTime(job.snapshot_time)}</small>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (error) {
            console.error('Error loading jobs:', error);
            document.getElementById('jobs-container').innerHTML =
                '<div class="alert alert-danger">Ошибка загрузки джобов</div>';
        }
    }
};

// Модальные окна
const Modal = {
    // Показать модальное окно добавления кластера
    showAddCluster() {
        document.getElementById('addClusterForm').reset();
        document.getElementById('cluster-active').checked = true;
        document.getElementById('addClusterModalLabel').textContent = 'Добавить кластер';
        document.getElementById('addClusterBtn').textContent = 'Добавить';
        document.getElementById('addClusterBtn').onclick = Actions.addCluster;

        new bootstrap.Modal(document.getElementById('addClusterModal')).show();
    },

    // Показать модальное окно редактирования кластера
    showEditCluster(cluster) {
        document.getElementById('cluster-name').value = cluster.name;
        document.getElementById('cluster-url').value = cluster.url;
        document.getElementById('cluster-description').value = cluster.description || '';
        document.getElementById('cluster-active').checked = cluster.is_active;
        document.getElementById('addClusterModalLabel').textContent = 'Редактировать кластер';
        document.getElementById('addClusterBtn').textContent = 'Сохранить';
        document.getElementById('addClusterBtn').onclick = () => Actions.updateCluster(cluster.id);

        new bootstrap.Modal(document.getElementById('addClusterModal')).show();
    }
};

// Действия
const Actions = {
    // Добавить кластер
    async addCluster() {
        const clusterData = {
            name: document.getElementById('cluster-name').value.trim(),
            url: document.getElementById('cluster-url').value.trim(),
            description: document.getElementById('cluster-description').value.trim(),
            is_active: document.getElementById('cluster-active').checked
        };

        if (!clusterData.name || !clusterData.url) {
            Utils.showNotification('Заполните обязательные поля', 'warning');
            return;
        }

        try {
            await API.createCluster(clusterData);
            bootstrap.Modal.getInstance(document.getElementById('addClusterModal')).hide();
            Utils.showNotification('Кластер успешно добавлен', 'success');
            await App.refreshData();
        } catch (error) {
            Utils.showNotification('Ошибка добавления кластера: ' + error.message, 'danger');
        }
    },

    // Обновить кластер
    async updateCluster(clusterId) {
        const clusterData = {
            name: document.getElementById('cluster-name').value.trim(),
            url: document.getElementById('cluster-url').value.trim(),
            description: document.getElementById('cluster-description').value.trim(),
            is_active: document.getElementById('cluster-active').checked
        };

        if (!clusterData.name || !clusterData.url) {
            Utils.showNotification('Заполните обязательные поля', 'warning');
            return;
        }

        try {
            await API.updateCluster(clusterId, clusterData);
            bootstrap.Modal.getInstance(document.getElementById('addClusterModal')).hide();
            Utils.showNotification('Кластер успешно обновлен', 'success');
            await App.refreshData();
        } catch (error) {
            Utils.showNotification('Ошибка обновления кластера: ' + error.message, 'danger');
        }
    },

    // Переключить состояние кластера
    async toggleCluster(clusterId, isActive) {
        try {
            const action = isActive ? 'deactivate' : 'activate';
            await API.toggleCluster(clusterId, action);
            Utils.showNotification(`Кластер ${isActive ? 'деактивирован' : 'активирован'}`, 'success');
            await App.refreshData();
        } catch (error) {
            Utils.showNotification('Ошибка изменения состояния кластера: ' + error.message, 'danger');
        }
    },

    // Удалить кластер
    async deleteCluster(clusterId, clusterName) {
        if (!confirm(`Удалить кластер "${clusterName}"?\n\nЭто действие нельзя отменить.`)) {
            return;
        }

        try {
            await API.deleteCluster(clusterId);
            Utils.showNotification(`Кластер "${clusterName}" удален`, 'success');
            await App.refreshData();
        } catch (error) {
            Utils.showNotification('Ошибка удаления кластера: ' + error.message, 'danger');
        }
    },

    // Запустить сбор данных
    async collectData() {
        try {
            await API.collectData();
            Utils.showNotification('Сбор данных запущен в фоновом режиме', 'info');
        } catch (error) {
            Utils.showNotification('Ошибка запуска сбора данных: ' + error.message, 'danger');
        }
    }
};

// Главное приложение
const App = {
    // Обновить все данные
    async refreshData() {
        if (isRefreshing) return;

        isRefreshing = true;
        const button = document.querySelector('.refresh-btn i');
        button.classList.add('fa-spin');

        try {
            await Promise.all([
                UI.loadStats(),
                UI.loadClusters(),
                UI.loadJobs()
            ]);
        } catch (error) {
            console.error('Error refreshing data:', error);
            Utils.showNotification('Ошибка обновления данных', 'danger');
        } finally {
            button.classList.remove('fa-spin');
            isRefreshing = false;
        }
    },

    // Запустить автообновление
    startAutoRefresh(intervalSeconds = 30) {
        if (refreshInterval) {
            clearInterval(refreshInterval);
        }

        refreshInterval = setInterval(() => {
            this.refreshData();
        }, intervalSeconds * 1000);
    },

    // Остановить автообновление
    stopAutoRefresh() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }
    },

    // Инициализация приложения
    async init() {
        console.log('🚀 Инициализация Flink Observer Dashboard');

        // Первоначальная загрузка данных
        await this.refreshData();

        // Запуск автообновления
        this.startAutoRefresh(30);

        // Проверка здоровья системы
        try {
            const health = await API.healthCheck();
            if (health.status !== 'healthy') {
                Utils.showNotification('Система работает некорректно', 'warning');
            }
        } catch (error) {
            console.error('Health check failed:', error);
        }

        console.log('✅ Dashboard инициализирован');
    }
};

// Глобальные функции для HTML
window.showAddClusterModal = Modal.showAddCluster;
window.addCluster = Actions.addCluster;
window.toggleCluster = Actions.toggleCluster;
window.deleteCluster = Actions.deleteCluster;
window.refreshData = App.refreshData;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Обработка видимости страницы
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        App.stopAutoRefresh();
    } else {
        App.startAutoRefresh(30);
        App.refreshData();
    }
});
