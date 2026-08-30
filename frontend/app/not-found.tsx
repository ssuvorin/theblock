import Link from "next/link";
import { buttonClassName } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <main id="main-content" className="page page-narrow">
      <div className="empty-state">
        <h1>Page not found</h1>
        <p>The requested workspace surface does not exist.</p>
        <Link className={buttonClassName("primary")} href="/query">Return to Ask</Link>
      </div>
    </main>
  );
}
