import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-[rgba(94,106,210,0.15)] text-accent",
        secondary: "bg-[rgba(255,255,255,0.06)] text-text-secondary",
        destructive: "bg-[rgba(239,68,68,0.15)] text-destructive",
        outline: "border border-border text-text-secondary",
        success: "bg-[rgba(16,185,129,0.15)] text-success",
        warning: "bg-[rgba(245,158,11,0.15)] text-warning",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
