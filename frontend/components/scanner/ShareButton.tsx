"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { createShareLink, revokeShareLink } from "@/lib/api/scan";

interface ShareButtonProps {
  scanDbId: string;
}

export function ShareButton({ scanDbId }: ShareButtonProps) {
  const queryClient = useQueryClient();
  const cacheKey = ["share", scanDbId];

  const cachedShare = queryClient.getQueryData<{ share_url: string; expires_at: string }>(cacheKey);
  const [shareUrl, setShareUrl] = useState<string | null>(cachedShare?.share_url ?? null);

  const shareMutation = useMutation({
    mutationFn: () => createShareLink(scanDbId),
    onSuccess: (data) => {
      queryClient.setQueryData(cacheKey, data);
      setShareUrl(data.share_url);
      navigator.clipboard.writeText(data.share_url).catch(() => null);
      toast.success("Link copiado al portapapeles");
    },
    onError: () => {
      toast.error("No se pudo generar el link");
    },
  });

  const revokeMutation = useMutation({
    mutationFn: () => revokeShareLink(scanDbId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: cacheKey });
      setShareUrl(null);
      toast.success("Link revocado");
    },
    onError: () => {
      toast.error("No se pudo revocar el link");
    },
  });

  const handleShare = () => {
    if (shareUrl) {
      navigator.clipboard.writeText(shareUrl).catch(() => null);
      toast.success("Link copiado al portapapeles");
      return;
    }
    shareMutation.mutate();
  };

  return (
    <div className="flex gap-2">
      <button
        onClick={handleShare}
        disabled={shareMutation.isPending}
        className="text-sm font-medium text-subtext hover:text-text transition-colors"
      >
        {shareMutation.isPending ? "Generando..." : "Compartir"}
      </button>

      {shareUrl && (
        <button
          onClick={() => revokeMutation.mutate()}
          disabled={revokeMutation.isPending}
          className="text-sm font-medium text-red-400 hover:text-red-600 transition-colors"
        >
          {revokeMutation.isPending ? "Revocando..." : "Revocar link"}
        </button>
      )}
    </div>
  );
}
