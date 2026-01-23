import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"

import { cn } from "@/lib/utils"

interface ProgressProps extends React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> {
  value?: number;
  indeterminate?: boolean;
}

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  ProgressProps
>(({ className, value, indeterminate = false, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn(
      "relative h-2 w-full overflow-hidden rounded-full bg-primary/20",
      className
    )}
    {...props}
  >
    {indeterminate ? (
      <div
        className="h-full bg-primary rounded-full"
        style={{
          width: '40%',
          animation: 'indeterminate-slide 1.5s ease-in-out infinite',
        }}
      />
    ) : (
      <ProgressPrimitive.Indicator
        className="h-full flex-1 bg-primary transition-all"
        style={{ width: '100%', transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    )}
    <style>{`
      @keyframes indeterminate-slide {
        0% { transform: translateX(-100%); }
        50% { transform: translateX(150%); }
        100% { transform: translateX(-100%); }
      }
    `}</style>
  </ProgressPrimitive.Root>
))
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
