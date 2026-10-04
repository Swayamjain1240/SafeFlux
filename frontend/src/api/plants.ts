import { apiDelete, apiGet, apiPatch, apiPost } from './client'
import type {
  PlantCreatePayload,
  PlantDetailResponse,
  PlantListResponse,
  PlantStateResponse,
} from '../types/plant'

/**
 * Plant configuration API — mirrors /api/v1/plants/* (Backend/app/api/routes/plants.py).
 * The server is the authorization boundary; every call relies on the session
 * cookie (withCredentials), never on a client-supplied owner id.
 */

export function fetchPlants(): Promise<PlantListResponse> {
  return apiGet<PlantListResponse>('/plants')
}

export function fetchPlant(plantId: string): Promise<PlantDetailResponse> {
  return apiGet<PlantDetailResponse>(`/plants/${encodeURIComponent(plantId)}`)
}

export function createPlant(payload: PlantCreatePayload): Promise<PlantDetailResponse> {
  return apiPost<PlantDetailResponse>('/plants', payload)
}

export function updatePlant(
  plantId: string,
  payload: Partial<PlantCreatePayload>,
): Promise<PlantDetailResponse> {
  return apiPatch<PlantDetailResponse>(`/plants/${encodeURIComponent(plantId)}`, payload)
}

export function deletePlant(plantId: string): Promise<void> {
  return apiDelete(`/plants/${encodeURIComponent(plantId)}`)
}

export function fetchPlantState(plantId: string): Promise<PlantStateResponse> {
  return apiGet<PlantStateResponse>(`/plants/${encodeURIComponent(plantId)}/state`)
}
