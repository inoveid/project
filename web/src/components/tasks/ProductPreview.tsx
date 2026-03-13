import { useEffect, useState } from 'react';
import { getProduct, getProductFiles, type ProductFile } from '../../api/products';
import type { Product } from '../../types';

interface ProductPreviewProps {
  productId: string;
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  ready: { label: 'Ready', color: 'bg-green-100 text-green-700' },
  cloning: { label: 'Cloning…', color: 'bg-yellow-100 text-yellow-700' },
  pending: { label: 'Pending', color: 'bg-gray-100 text-gray-500' },
  error: { label: 'Error', color: 'bg-red-100 text-red-700' },
};

export function ProductPreview({ productId }: ProductPreviewProps) {
  const [product, setProduct] = useState<Product | null>(null);
  const [files, setFiles] = useState<ProductFile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getProduct(productId),
      getProductFiles(productId),
    ])
      .then(([p, f]) => {
        setProduct(p);
        setFiles(f);
      })
      .finally(() => setLoading(false));
  }, [productId]);

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 animate-pulse">
        <div className="h-4 w-32 bg-gray-200 rounded" />
      </div>
    );
  }

  if (!product) return null;

  const statusCfg = STATUS_MAP[product.status] ?? STATUS_MAP["pending"]!;
  const displayFiles = files.slice(0, 7);
  const hasMore = files.length > 7;

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-800">{product.name}</span>
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${statusCfg.color}`}>
          {statusCfg.label}
        </span>
      </div>

      {/* Git URL */}
      {product.git_url && (
        <p className="text-[11px] text-gray-400 truncate">{product.git_url}</p>
      )}

      {/* Files */}
      {displayFiles.length > 0 ? (
        <div className="space-y-0.5">
          {displayFiles.map((f) => (
            <div key={f.name} className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="text-gray-400 w-3.5 text-center">
                {f.type === 'dir' ? '\u{1F4C1}' : '\u{1F4C4}'}
              </span>
              <span className="truncate">{f.name}</span>
              {f.type === 'file' && f.size > 0 && (
                <span className="text-gray-300 ml-auto text-[10px] shrink-0">
                  {formatSize(f.size)}
                </span>
              )}
            </div>
          ))}
          {hasMore && (
            <p className="text-[10px] text-gray-400 pl-5">
              +{files.length - 7} more
            </p>
          )}
        </div>
      ) : (
        <p className="text-xs text-gray-400 italic">No files</p>
      )}
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
