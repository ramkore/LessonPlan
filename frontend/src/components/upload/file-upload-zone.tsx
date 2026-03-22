"use client";

import { useCallback, useRef, useState } from "react";
import { CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { UploadIcon, Loader2Icon, FileIcon } from "lucide-react";

interface FileUploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
  isLoading?: boolean;
}

export function FileUploadZone({
  onUpload,
  accept,
  isLoading = false,
}: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setSelectedFile(file.name);
      await onUpload(file);
      setSelectedFile(null);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    },
    [onUpload]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!isLoading) setIsDragOver(true);
    },
    [isLoading]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      if (isLoading) return;
      const file = e.dataTransfer.files?.[0];
      if (file) await handleFile(file);
    },
    [isLoading, handleFile]
  );

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) await handleFile(file);
    },
    [handleFile]
  );

  return (
    <CardContent>
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isLoading && inputRef.current?.click()}
        className={cn(
          "relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 text-center transition-colors cursor-pointer",
          isDragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50",
          isLoading && "pointer-events-none opacity-60"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleFileChange}
          className="hidden"
          disabled={isLoading}
        />

        {isLoading ? (
          <>
            <Loader2Icon className="size-8 text-muted-foreground animate-spin" />
            <div className="space-y-1">
              <p className="text-sm font-medium">Uploading...</p>
              {selectedFile && (
                <p className="text-xs text-muted-foreground flex items-center gap-1.5 justify-center">
                  <FileIcon className="size-3" />
                  {selectedFile}
                </p>
              )}
            </div>
          </>
        ) : (
          <>
            <UploadIcon className="size-8 text-muted-foreground" />
            <div className="space-y-1">
              <p className="text-sm font-medium">
                Drop a file here or click to browse
              </p>
              <p className="text-xs text-muted-foreground">
                {accept
                  ? `Accepted formats: ${accept}`
                  : "All file types accepted"}
              </p>
            </div>
          </>
        )}
      </div>
    </CardContent>
  );
}
