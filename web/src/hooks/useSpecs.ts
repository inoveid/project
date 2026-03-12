import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSpec,
  deleteSpec,
  getSpec,
  getSpecs,
  getSpecVersions,
  rollbackSpec,
  updateSpec,
} from '../api/specs';
import type { SpecCreate, SpecUpdate } from '../types';

const SPECS_KEY = ['specs'] as const;

export function useSpecs(productId: string) {
  return useQuery({
    queryKey: [...SPECS_KEY, 'list', productId],
    queryFn: () => getSpecs(productId),
    enabled: !!productId,
  });
}

export function useSpec(id: string) {
  return useQuery({
    queryKey: [...SPECS_KEY, 'detail', id],
    queryFn: () => getSpec(id),
    enabled: !!id,
  });
}

export function useSpecVersions(specId: string) {
  return useQuery({
    queryKey: [...SPECS_KEY, 'versions', specId],
    queryFn: () => getSpecVersions(specId),
    enabled: !!specId,
  });
}

export function useCreateSpec() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ productId, data }: { productId: string; data: SpecCreate }) =>
      createSpec(productId, data),
    onSuccess: (spec) => {
      void queryClient.invalidateQueries({ queryKey: [...SPECS_KEY, 'list', spec.product_id] });
    },
  });
}

export function useUpdateSpec() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SpecUpdate }) => updateSpec(id, data),
    onSuccess: (spec) => {
      void queryClient.invalidateQueries({ queryKey: [...SPECS_KEY, 'list', spec.product_id] });
      void queryClient.invalidateQueries({ queryKey: [...SPECS_KEY, 'detail', spec.id] });
      void queryClient.invalidateQueries({ queryKey: [...SPECS_KEY, 'versions', spec.id] });
    },
  });
}

export function useDeleteSpec() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSpec(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SPECS_KEY });
    },
  });
}

export function useRollbackSpec() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ specId, version }: { specId: string; version: number }) =>
      rollbackSpec(specId, version),
    onSuccess: (spec) => {
      void queryClient.invalidateQueries({ queryKey: [...SPECS_KEY, 'list', spec.product_id] });
      void queryClient.invalidateQueries({ queryKey: [...SPECS_KEY, 'detail', spec.id] });
      void queryClient.invalidateQueries({ queryKey: [...SPECS_KEY, 'versions', spec.id] });
    },
  });
}
