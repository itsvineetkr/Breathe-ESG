import client from './client'

export const uploadFile = (formData) =>
  client.post('/ingestion/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

export const getSources = (params) => client.get('/ingestion/sources/', { params })
export const getSourceDetail = (id) => client.get(`/ingestion/sources/${id}/`)
