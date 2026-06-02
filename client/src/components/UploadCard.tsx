import { useRef, useState } from 'react';
import { UploadCloud, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const MAX_FILE_SIZE_MB = 50;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

interface Props {
  onUpload: (file: File) => Promise<void>;
  isProcessingActive: boolean;
  isUploading: boolean;
}

export function UploadCard({ onUpload, isProcessingActive, isUploading }: Props) {
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function validate(file: File): boolean {
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Invalid file format. Please upload a PDF.');
      return false;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      toast.error(`File size exceeds the ${MAX_FILE_SIZE_MB}MB limit.`);
      return false;
    }
    return true;
  }

  function handleDrag(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (isProcessingActive) return;
    setIsDragActive(e.type === 'dragenter' || e.type === 'dragover');
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (isProcessingActive) return;
    const file = e.dataTransfer.files?.[0];
    if (file && validate(file)) onUpload(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file && validate(file)) onUpload(file);
    e.target.value = '';
  }

  const disabled = isProcessingActive || isUploading;

  return (
    <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/80 rounded-2xl p-6 shadow-xl relative overflow-hidden">
      <div className="absolute -top-24 -left-24 w-48 h-48 bg-indigo-500/5 blur-[80px] rounded-full" />
      <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-purple-500/5 blur-[80px] rounded-full" />

      <h2 className="text-base font-semibold text-slate-200 mb-1">Upload Document</h2>
      <p className="text-xs text-slate-400 mb-4">
        Upload large PDFs (up to 50MB) to generate executive-level analysis.
      </p>

      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-3 transition-all cursor-pointer ${
          disabled
            ? 'border-slate-800 bg-slate-950/40 opacity-55 cursor-not-allowed'
            : isDragActive
              ? 'border-indigo-500 bg-indigo-500/5 shadow-inner'
              : 'border-slate-800 hover:border-slate-700 bg-slate-950/60 hover:bg-slate-950/80'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf"
          onChange={handleFileChange}
          disabled={disabled}
        />

        <div className={`p-4 rounded-full bg-slate-900 border transition-all ${
          isDragActive ? 'border-indigo-500 text-indigo-400 scale-110' : 'border-slate-800 text-slate-400'
        }`}>
          {isUploading
            ? <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
            : <UploadCloud className="w-8 h-8" />
          }
        </div>

        <div className="text-center">
          <p className="text-sm font-medium text-slate-300">
            {isUploading
              ? 'Uploading file...'
              : isProcessingActive
                ? 'Upload disabled during processing'
                : 'Drag & drop PDF here'}
          </p>
          {!disabled && (
            <p className="text-xs text-slate-500 mt-1">or click to browse from folders</p>
          )}
        </div>

        <div className="border-t border-slate-900 w-full pt-3 mt-1 flex justify-around text-[10px] text-slate-400 font-mono">
          <span>Format: PDF</span>
          <span>Max Size: 50 MB</span>
        </div>
      </div>
    </div>
  );
}
