import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { LanguageRoot } from "./i18n";
import { Shell } from "./components/Shell";
import { Dashboard } from "./pages/Dashboard";
import { PixelArt } from "./pages/PixelArt";
import { Sprites } from "./pages/Sprites";
import { Tileset } from "./pages/Tileset";
import { Procedural } from "./pages/Procedural";
import { False3D } from "./pages/False3D";
import { AnimationStudio } from "./pages/Animation";
import { Library } from "./pages/Library";
import { Projects } from "./pages/Projects";
import { Settings } from "./pages/Settings";
import { Style } from "./pages/Style";

export default function App() {
  return (
    <LanguageRoot>
      <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pixelart" element={<PixelArt />} />
          <Route path="/sprites" element={<Sprites />} />
          <Route path="/tileset" element={<Tileset />} />
          <Route path="/procedural" element={<Procedural />} />
          <Route path="/false3d" element={<False3D />} />
          <Route path="/animation" element={<AnimationStudio />} />
          <Route path="/library" element={<Library />} />
          <Route path="/style" element={<Style />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      </BrowserRouter>
    </LanguageRoot>
  );
}
