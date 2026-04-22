interface AuthAlertProps {
  type: "401" | "409" | "429";
}

const MESSAGES: Record<AuthAlertProps["type"], { code: string; text: string; colors: { bg: string; border: string; color: string } }> = {
  "401": {
    code: "[ERROR_401]",
    text: "Credenciales inválidas. Verifica tus datos.",
    colors: {
      bg: "rgba(248,113,113,0.08)",
      border: "rgba(248,113,113,0.3)",
      color: "#F87171",
    },
  },
  "409": {
    code: "[ERROR_409]",
    text: "Email ya registrado.",
    colors: {
      bg: "rgba(248,113,113,0.08)",
      border: "rgba(248,113,113,0.3)",
      color: "#F87171",
    },
  },
  "429": {
    code: "[ERROR_429]",
    text: "Demasiados intentos. Espera 60 segundos.",
    colors: {
      bg: "rgba(252,211,77,0.08)",
      border: "rgba(252,211,77,0.3)",
      color: "#FCD34D",
    },
  },
};

export function AuthAlert({ type }: AuthAlertProps) {
  const { code, text, colors } = MESSAGES[type];

  return (
    <div
      className="rounded-input px-4 py-3 font-mono text-[11.5px]"
      style={{
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        color: colors.color,
      }}
      role="alert"
    >
      <span className="font-bold">{code}</span>{" "}
      <span className="font-normal">{text}</span>
    </div>
  );
}
