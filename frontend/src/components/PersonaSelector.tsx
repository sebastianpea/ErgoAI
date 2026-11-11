import type { Imagen } from "../types/caso";

interface Props {
  imagen: Imagen;
  mostrar: boolean;
  onMostrar: (mostrar: boolean) => void;
  onSeleccionar: (id: string | null) => void;
  disabled?: boolean;
}

export function PersonaSelector({ imagen, mostrar, onMostrar, onSeleccionar, disabled }: Props) {
  return <div>
    <label><input type="checkbox" role="switch" checked={mostrar}
      onChange={e => onMostrar(e.target.checked)} /> Mostrar esqueleto</label>
    {!!imagen.personas?.length && <label>Persona de esta imagen
      <select value={imagen.persona_seleccionada ?? ""} disabled={disabled}
        onChange={e => onSeleccionar(e.target.value || null)}>
        <option value="">Todas (solo visualización)</option>
        {imagen.personas.map(p => <option key={p.id} value={p.id}>{p.id}</option>)}
      </select>
    </label>}
    <p className="sutil">Selecciona el objetivo manualmente en cada vista. Los IDs no identifican a la misma persona entre imágenes.</p>
  </div>;
}
