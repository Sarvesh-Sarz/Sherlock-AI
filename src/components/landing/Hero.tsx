/**
 * Page title and subtitle. Static content — no props, since the title
 * and tagline don't change with app state.
 */
export function Hero() {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <h1 className="font-display text-5xl font-medium tracking-tight text-case-text sm:text-6xl">
        Sherlock AI
      </h1>
      <p className="font-display text-lg italic text-case-muted">
        Find the Cause. Fix the Future.
      </p>
    </div>
  );
}
