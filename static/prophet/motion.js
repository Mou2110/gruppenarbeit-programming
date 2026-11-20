const PORTRAIT_WIDTH = 1122;
const PORTRAIT_HEIGHT = 1402;
const LIFT_MS = 2000;

// Matching points on the hairline, brows, eyes, nose, lips and beard.
// Each entry maps a point in the lowered portrait to the lifted portrait.
const faceTracks = [
  [470, 300, 464, 265], [650, 265, 638, 230], [785, 307, 777, 275],
  [544, 417, 532, 361], [708, 384, 699, 333],
  [552, 443, 543, 386], [727, 420, 712, 372],
  [520, 502, 507, 450], [770, 505, 758, 456],
  [640, 555, 625, 512], [646, 615, 628, 567],
  [600, 662, 573, 616], [797, 645, 783, 604],
  [693, 733, 664, 685],
];

function liftedPoint(x, y) {
  let dx = 0;
  let dy = 0;
  let totalWeight = 0;
  for (const [fromX, fromY, toX, toY] of faceTracks) {
    const distanceSquared = (x - fromX) ** 2 + (y - fromY) ** 2;
    const weight = 1 / (distanceSquared + 720) ** 2;
    dx += (toX - fromX) * weight;
    dy += (toY - fromY) * weight;
    totalWeight += weight;
  }
  const radius = Math.hypot((x - 649) / 325, (y - 473) / 407);
  const edge = Math.min(1, Math.max(0, (1 - radius) / 0.37));
  const influence = edge * edge * (3 - 2 * edge) / totalWeight;
  return [(x + dx * influence) / PORTRAIT_WIDTH, (y + dy * influence) / PORTRAIT_HEIGHT];
}

function makeMesh() {
  const columns = 36;
  const rows = 45;
  const vertices = [];
  const faces = [];
  for (let row = 0; row <= rows; row++) {
    for (let col = 0; col <= columns; col++) {
      const x = col / columns;
      const y = row / rows;
      vertices.push(x, y, ...liftedPoint(x * PORTRAIT_WIDTH, y * PORTRAIT_HEIGHT));
      if (col < columns && row < rows) {
        const a = row * (columns + 1) + col;
        const b = a + columns + 1;
        faces.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
  }
  return {vertices: new Float32Array(vertices), faces: new Uint16Array(faces)};
}

function makeProgram(gl) {
  const vertexSource = `
    attribute vec2 loweredPoint, liftedPoint;
    uniform mediump float progress;
    varying mediump vec2 loweredUV, liftedUV;
    void main() {
      loweredUV = loweredPoint;
      liftedUV = liftedPoint;
      vec2 framePoint = mix(loweredUV, liftedUV, progress);
      gl_Position = vec4(framePoint * vec2(2.0, -2.0) + vec2(-1.0, 1.0), 0.0, 1.0);
    }
  `;
  const fragmentSource = `
    precision mediump float;
    varying mediump vec2 loweredUV, liftedUV;
    uniform sampler2D loweredImage, liftedImage;
    uniform mediump float progress;
    void main() {
      vec4 lowered = texture2D(loweredImage, loweredUV);
      vec4 lifted = texture2D(liftedImage, liftedUV);
      gl_FragColor = mix(lowered, lifted, progress);
    }
  `;
  const program = gl.createProgram();
  for (const [type, source] of [[gl.VERTEX_SHADER, vertexSource], [gl.FRAGMENT_SHADER, fragmentSource]]) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    gl.attachShader(program, shader);
    gl.deleteShader(shader);
  }
  gl.linkProgram(program);
  return gl.getProgramParameter(program, gl.LINK_STATUS) ? program : null;
}

export async function animatePortrait(splash) {
  if (!splash || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const canvas = splash.querySelector('.prophet-motion-canvas');
  const images = [...splash.querySelectorAll('.prophecy-portrait img')];
  await Promise.all(images.map(image => image.decode()));
  const {width, height} = canvas.getBoundingClientRect();
  const coverWidth = Math.max(width, height * PORTRAIT_WIDTH / PORTRAIT_HEIGHT);
  canvas.width = Math.max(1, Math.min(canvas.width, Math.round(coverWidth * devicePixelRatio)));
  canvas.height = Math.max(1, Math.round(canvas.width * PORTRAIT_HEIGHT / PORTRAIT_WIDTH));
  const gl = canvas.getContext('webgl', {alpha: false, depth: false, antialias: false});
  const program = gl && makeProgram(gl);
  if (!program) {
    splash.classList.add('prophecy-fallback');
    return;
  }
  gl.useProgram(program);

  const {vertices, faces} = makeMesh();
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, faces, gl.STATIC_DRAW);

  ['loweredPoint', 'liftedPoint'].forEach((name, index) => {
    const location = gl.getAttribLocation(program, name);
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 16, index * 8);
  });
  ['loweredImage', 'liftedImage'].forEach((name, index) => {
    gl.activeTexture(gl.TEXTURE0 + index);
    gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, images[index]);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.uniform1i(gl.getUniformLocation(program, name), index);
  });
  gl.viewport(0, 0, canvas.width, canvas.height);
  const progress = gl.getUniformLocation(program, 'progress');

  function settle() {
    splash.classList.remove('prophecy-interpolated');
    splash.classList.add('prophecy-settled');
  }

  let startedAt;

  function frame(now) {
    if (!splash.isConnected || gl.isContextLost()) return;
    startedAt ??= now;
    const time = (now - startedAt) / LIFT_MS;
    if (time >= 1) {
      settle();
      return;
    }
    // Match the endpoint velocity to the still portraits for a smooth start and stop.
    const lift = time * time * (3 - 2 * time);
    gl.uniform1f(progress, lift);
    gl.drawElements(gl.TRIANGLES, faces.length, gl.UNSIGNED_SHORT, 0);
    requestAnimationFrame(frame);
  }
  canvas.addEventListener('webglcontextlost', settle, {once: true});
  requestAnimationFrame(now => {
    frame(now);
    splash.classList.add('prophecy-interpolated');
  });
}
