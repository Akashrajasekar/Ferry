import type { ReactNode } from 'react';
import { useReveal } from '../hooks/useReveal';

interface Props {
  children: ReactNode;
}

export function Reveal({ children }: Props) {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} className={`reveal ${revealed ? 'revealed' : ''}`}>
      {children}
    </div>
  );
}
