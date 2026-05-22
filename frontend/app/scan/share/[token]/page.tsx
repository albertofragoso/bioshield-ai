import { notFound } from "next/navigation";
import { getSharedScan } from "@/lib/api/scan";

interface SharedScanPageProps {
  params: Promise<{ token: string }>;
}

export default async function SharedScanPage({ params }: SharedScanPageProps) {
  const { token } = await params;
  let scan;
  let expired = false;

  try {
    scan = await getSharedScan(token);
  } catch (err) {
    if ((err as Error).message === "EXPIRED") {
      expired = true;
    } else {
      notFound();
    }
  }

  if (expired) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="text-center space-y-4">
          <p className="text-lg font-semibold">Este link ha expirado</p>
          <p className="text-sm text-subtext">
            El propietario puede generar un nuevo link desde su historial.
          </p>
        </div>
      </main>
    );
  }

  if (!scan) notFound();

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-xl mx-auto px-4 py-6 space-y-4">
        <div className="text-xs text-subtext font-mono text-center">
          Resultado compartido
        </div>

        <div className="space-y-2">
          <div className="text-center">
            <span
              className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${
                scan.semaphore === "GREEN"
                  ? "bg-green-100 text-green-800"
                  : scan.semaphore === "YELLOW"
                  ? "bg-yellow-100 text-yellow-800"
                  : scan.semaphore === "RED"
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {scan.semaphore}
            </span>
          </div>

          {scan.product_name && (
            <h1 className="text-xl font-bold text-center">{scan.product_name}</h1>
          )}

          <p className="text-sm text-subtext text-center font-mono">
            {scan.product_barcode}
          </p>
        </div>

        {scan.ingredients.length > 0 && (
          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-subtext uppercase tracking-wider">
              Ingredientes
            </h2>
            <ul className="space-y-1">
              {scan.ingredients.map((ing, i) => (
                <li key={i} className="text-sm">
                  {ing.name}
                </li>
              ))}
            </ul>
          </section>
        )}

        <p className="text-xs text-subtext text-center">
          Escaneado el{" "}
          {new Date(scan.scanned_at).toLocaleDateString("es-MX", {
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        </p>
      </div>
    </main>
  );
}
