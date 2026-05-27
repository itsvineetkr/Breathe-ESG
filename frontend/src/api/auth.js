import client from './client'

export const register = (data) => client.post('/auth/register/', data)
export const login = (email, password) => client.post('/auth/login/', { email, password })
export const getMe = () => client.get('/auth/me/')
export const getAnalysts = () => client.get('/auth/analysts/')
export const addAnalyst = (data) => client.post('/auth/analysts/add/', data)
export const removeAnalyst = (id) => client.delete(`/auth/analysts/${id}/remove/`)
export const updateOrg = (data) => client.patch('/auth/org/', data)
