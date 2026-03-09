import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  cloneProduct,
  createProduct,
  deleteProduct,
  getProduct,
  getProducts,
  updateProduct,
} from '../api/products';
import type { ProductCreate, ProductUpdate } from '../types';

const PRODUCTS_KEY = ['products'] as const;

export function useProducts(businessId: string) {
  return useQuery({
    queryKey: [...PRODUCTS_KEY, businessId],
    queryFn: () => getProducts(businessId),
    enabled: !!businessId,
  });
}

export function useProduct(id: string, polling = false) {
  return useQuery({
    queryKey: [...PRODUCTS_KEY, 'detail', id],
    queryFn: () => getProduct(id),
    enabled: !!id,
    refetchInterval: polling
      ? (query) => (query.state.data?.status === 'cloning' ? 2000 : false)
      : false,
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProductCreate) => createProduct(data),
    onSuccess: (product) => {
      void queryClient.invalidateQueries({ queryKey: [...PRODUCTS_KEY, product.business_id] });
    },
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProductUpdate }) => updateProduct(id, data),
    onSuccess: (product) => {
      void queryClient.invalidateQueries({ queryKey: [...PRODUCTS_KEY, product.business_id] });
      void queryClient.invalidateQueries({ queryKey: [...PRODUCTS_KEY, 'detail', product.id] });
    },
  });
}

export function useDeleteProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteProduct(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PRODUCTS_KEY });
    },
  });
}

export function useCloneProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cloneProduct(id),
    onSuccess: (product) => {
      queryClient.setQueryData([...PRODUCTS_KEY, 'detail', product.id], product);
      void queryClient.invalidateQueries({ queryKey: [...PRODUCTS_KEY, product.business_id] });
    },
  });
}
