import { Loader2 } from 'lucide-react';

interface Props {
  visible: boolean;
  stage?: string | null;
}

export function ProcessingBanner({ visible, stage }: Props) {
  if (!visible) return null;
  return (
    <div className="bg-amber-600/90 backdrop-blur-md text-amber-50 font-medium py-3 px-4 flex items-center justify-center gap-2 text-sm shadow-md animate-pulse border-b border-amber-500/20 sticky top-0 z-50">
      <Loader2 className="w-4 h-4 animate-spin text-white" />
      <span>{stage ?? "Processing active document... please wait."}</span>
    </div>
  );
}
