import client from './client'

export const getRecords = (params) => client.get('/emissions/records/', { params })
export const getRecord = (id) => client.get(`/emissions/records/${id}/`)
export const reviewRecord = (id, data) => client.post(`/emissions/records/${id}/review/`, data)
export const bulkReview = (data) => client.post('/emissions/records/bulk-review/', data)
export const getReports = (params) => client.get('/emissions/reports/', { params })
export const getAuditLogs = (params) => client.get('/audit/logs/', { params })
