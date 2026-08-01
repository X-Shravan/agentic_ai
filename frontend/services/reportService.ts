import { apiGet } from './api';

export function fetchReports() { return apiGet('/reports'); }
