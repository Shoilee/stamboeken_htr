let canvas;

function setupCanvas(imageUrl) {
  canvas = new fabric.Canvas('canvas', { selection: true });

  fabric.Image.fromURL(imageUrl, function(img) {
    img.scaleToWidth(800);
    canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
  });

  // Add polygon drawing
  let isDrawing = false;
  let polygonPoints = [];

  canvas.on('mouse:down', function(o) {
    if (!isDrawing) {
      isDrawing = true;
      polygonPoints = [o.pointer];
    } else {
      polygonPoints.push(o.pointer);
    }
  });

  canvas.on('mouse:dblclick', function() {
    isDrawing = false;
    const polygon = new fabric.Polygon(polygonPoints, {
      fill: 'rgba(255,165,0,0.3)',
      stroke: 'orange',
      strokeWidth: 2,
      selectable: true
    });
    canvas.add(polygon);
    polygonPoints = [];
  });

  document.getElementById('save').onclick = function() {
    const polygons = canvas.getObjects('polygon').map(p => ({
      points: p.points.map(pt => ({x: pt.x, y: pt.y}))
    }));
    fetch('/save_polygons', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({polygons})
    }).then(res => res.json()).then(data => alert(data.message));
  };

  document.getElementById('run').onclick = function() {
    fetch('/run_pipeline', { method: 'POST' })
      .then(res => res.json())
      .then(data => alert(data.message || data.error));
  };
}
