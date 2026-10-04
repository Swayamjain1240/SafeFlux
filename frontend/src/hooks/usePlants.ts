import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createPlant,
  deletePlant,
  fetchPlant,
  fetchPlants,
  updatePlant,
} from '../api/plants'
import type { PlantCreatePayload, PlantDetailResponse } from '../types/plant'

/** Query key factory keeps cache invalidation consistent and typo-free. */
export const plantKeys = {
  all: ['plants'] as const,
  detail: (id: string) => ['plants', id] as const,
}

export function usePlantList() {
  return useQuery({
    queryKey: plantKeys.all,
    queryFn: fetchPlants,
  })
}

export function usePlant(plantId: string | null) {
  return useQuery({
    queryKey: plantKeys.detail(plantId ?? ''),
    queryFn: () => fetchPlant(plantId as string),
    enabled: Boolean(plantId),
  })
}

export function useCreatePlant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PlantCreatePayload) => createPlant(payload),
    onSuccess: (data: PlantDetailResponse) => {
      queryClient.setQueryData(plantKeys.detail(data.plant.id), data)
      void queryClient.invalidateQueries({ queryKey: plantKeys.all })
    },
  })
}

export function useUpdatePlant(plantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<PlantCreatePayload>) => updatePlant(plantId, payload),
    onSuccess: (data: PlantDetailResponse) => {
      queryClient.setQueryData(plantKeys.detail(data.plant.id), data)
      void queryClient.invalidateQueries({ queryKey: plantKeys.all })
    },
  })
}

export function useDeletePlant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (plantId: string) => deletePlant(plantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: plantKeys.all })
    },
  })
}
