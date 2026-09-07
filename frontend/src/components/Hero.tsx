import { LowPoly } from "@/components/LowPoly";

/** Page header band. The low-poly facets sit behind the text, never over it. */
export function Hero({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-[16px] border border-line bg-surface px-5 py-5 sm:px-6 sm:py-6">
      {/* Hidden on a phone, where the facets would sit under the text rather than beside it. */}
      <LowPoly
        variant="corner"
        className="absolute right-0 top-0 hidden h-full w-[46%] opacity-90 sm:block"
      />
      <div className="relative flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-xl">
          <h1 className="text-[19px] font-semibold tracking-tight text-ink sm:text-[22px]">
            {title}
          </h1>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft sm:text-[13.5px]">
            {body}
          </p>
        </div>
        {action}
      </div>
    </div>
  );
}
