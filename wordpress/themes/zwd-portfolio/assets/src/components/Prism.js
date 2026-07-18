import { Mesh, Program, Renderer, Triangle } from 'ogl';

const vertex = `attribute vec2 position;void main(){gl_Position=vec4(position,0.,1.);}`;
const fragment = `
precision highp float;
uniform vec2 uResolution;
uniform float uTime;
void main(){
  vec2 uv=(gl_FragCoord.xy-.5*uResolution.xy)/min(uResolution.x,uResolution.y);
  float angle=atan(uv.y,uv.x)+uTime*.04;
  float radius=length(uv);
  float rays=.5+.5*cos(angle*6.-radius*12.);
  float prism=smoothstep(.65,.05,radius)*rays;
  vec3 paper=vec3(.969,.969,.945);
  vec3 grey=vec3(.72,.71,.68);
  gl_FragColor=vec4(mix(paper,grey,prism*.22),1.);
}`;

export function mountPrism(container) {
  if (!container || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return () => {};
  let renderer;
  try {
    renderer = new Renderer({ dpr: Math.min(window.devicePixelRatio || 1, 1.5), alpha: false });
  } catch {
    container.classList.add('is-static');
    return () => {};
  }
  const gl = renderer.gl;
  const geometry = new Triangle(gl);
  const program = new Program(gl, {
    vertex,
    fragment,
    uniforms: { uResolution: { value: [1, 1] }, uTime: { value: 0 } },
  });
  const mesh = new Mesh(gl, { geometry, program });
  container.appendChild(gl.canvas);
  let frame = 0;
  let active = false;
  const resize = () => {
    renderer.setSize(container.clientWidth, container.clientHeight);
    program.uniforms.uResolution.value = [gl.canvas.width, gl.canvas.height];
  };
  const render = time => {
    if (!active || document.hidden) return;
    program.uniforms.uTime.value = time * .001;
    renderer.render({ scene: mesh });
    frame = requestAnimationFrame(render);
  };
  const observer = new IntersectionObserver(([entry]) => {
    active = entry.isIntersecting;
    cancelAnimationFrame(frame);
    if (active) frame = requestAnimationFrame(render);
  });
  observer.observe(container);
  resize();
  window.addEventListener('resize', resize);
  return () => {
    observer.disconnect();
    cancelAnimationFrame(frame);
    window.removeEventListener('resize', resize);
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    gl.canvas.remove();
  };
}
