import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Bandeja } from "./pages/Bandeja";
import { Dashboard } from "./pages/Dashboard";
import { Analisis } from "./pages/Analisis";
import { Plan } from "./pages/Plan";
import { Informe } from "./pages/Informe";
import { Alertas } from "./pages/Alertas";
import { Bitacora } from "./pages/Bitacora";
import { NuevoCaso } from "./pages/NuevoCaso";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="casos" element={<Bandeja />} />
        <Route path="casos/nuevo" element={<NuevoCaso />} />
        <Route path="casos/:id" element={<Analisis />} />
        <Route path="casos/:id/plan" element={<Plan />} />
        <Route path="casos/:id/informe" element={<Informe />} />
        <Route path="alertas" element={<Alertas />} />
        <Route path="bitacora" element={<Bitacora />} />
        <Route path="*" element={<p>Página no encontrada.</p>} />
      </Route>
    </Routes>
  );
}