import AppKit
// Finantsabi ikoon: tumevioletne gradient + tõusev joon
let size = 1024
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let ctx = NSGraphicsContext.current!.cgContext
let S = CGFloat(size)
let cs = CGColorSpaceCreateDeviceRGB()
// taust (täisruut – iOS/maskable lõikab ise nurgad)
let bg = CGGradient(colorsSpace: cs, colors: [CGColor(red:0.10,green:0.06,blue:0.20,alpha:1), CGColor(red:0.01,green:0.01,blue:0.03,alpha:1)] as CFArray, locations: [0,1])!
ctx.drawLinearGradient(bg, start: CGPoint(x:0,y:S), end: CGPoint(x:S,y:0), options: [])
// pehme helk
let glow = CGGradient(colorsSpace: cs, colors: [CGColor(red:0.64,green:0.45,blue:1,alpha:0.45), CGColor(red:0.64,green:0.45,blue:1,alpha:0)] as CFArray, locations: [0,1])!
ctx.drawRadialGradient(glow, startCenter: CGPoint(x:S*0.70,y:S*0.66), startRadius: 0, endCenter: CGPoint(x:S*0.70,y:S*0.66), endRadius: S*0.55, options: [])
// joon
let pts: [CGPoint] = [CGPoint(x:0.20,y:0.34), CGPoint(x:0.38,y:0.50), CGPoint(x:0.52,y:0.42), CGPoint(x:0.78,y:0.70)].map{ CGPoint(x:$0.x*S, y:$0.y*S) }
let path = CGMutablePath(); path.addLines(between: pts)
// täide joone all
let fill = CGMutablePath(); fill.addLines(between: pts); fill.addLine(to: CGPoint(x:0.78*S,y:0.22*S)); fill.addLine(to: CGPoint(x:0.20*S,y:0.22*S)); fill.closeSubpath()
ctx.saveGState(); ctx.addPath(fill); ctx.clip()
let fg = CGGradient(colorsSpace: cs, colors: [CGColor(red:0.21,green:0.89,blue:0.63,alpha:0.35), CGColor(red:0.21,green:0.89,blue:0.63,alpha:0)] as CFArray, locations: [0,1])!
ctx.drawLinearGradient(fg, start: CGPoint(x:0,y:0.70*S), end: CGPoint(x:0,y:0.22*S), options: [])
ctx.restoreGState()
ctx.setLineCap(.round); ctx.setLineJoin(.round)
ctx.setLineWidth(S*0.055)
ctx.setStrokeColor(CGColor(red:0.21,green:0.89,blue:0.63,alpha:1))
ctx.addPath(path); ctx.strokePath()
// tipupunkt
ctx.setFillColor(CGColor(red:0.96,green:0.95,blue:0.97,alpha:1))
ctx.fillEllipse(in: CGRect(x:0.78*S-S*0.05, y:0.70*S-S*0.05, width:S*0.10, height:S*0.10))
NSGraphicsContext.restoreGraphicsState()
let out = CommandLine.arguments[1]
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
