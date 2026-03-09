import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createBusiness,
  deleteBusiness,
  getBusiness,
  getBusinesses,
  updateBusiness,
} from '../api/businesses';
import type { BusinessCreate, BusinessUpdate } from '../types';

const BUSINESSES_KEY = ['businesses'] as const;

export function useBusinesses() {
  return useQuery({ queryKey: BUSINESSES_KEY, queryFn: getBusinesses });
}

export function useBusiness(id: string) {
  return useQuery({
    queryKey: [...BUSINESSES_KEY, id],
    queryFn: () => getBusiness(id),
    enabled: !!id,
  });
}

export function useCreateBusiness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BusinessCreate) => createBusiness(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: BUSINESSES_KEY });
    },
  });
}

export function useUpdateBusiness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: BusinessUpdate }) => updateBusiness(id, data),
    onSuccess: (_, { id }) => {
      void queryClient.invalidateQueries({ queryKey: BUSINESSES_KEY });
      void queryClient.invalidateQueries({ queryKey: [...BUSINESSES_KEY, id] });
    },
  });
}

export function useDeleteBusiness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) => deleteBusiness(id, force),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: BUSINESSES_KEY });
    },
  });
}
