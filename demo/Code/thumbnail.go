// Command thumbnail renders resized JPEG previews for Cloud image uploads.
package main

import (
	"flag"
	"fmt"
	"image"
	"image/jpeg"
	_ "image/png"
	"log"
	"os"
	"path/filepath"

	"golang.org/x/image/draw"
)

var sizes = []int{128, 256, 512}

func main() {
	src := flag.String("src", "", "source image")
	out := flag.String("out", "derived", "output directory")
	quality := flag.Int("quality", 82, "JPEG quality")
	flag.Parse()
	if *src == "" {
		log.Fatal("-src is required")
	}
	if err := render(*src, *out, *quality); err != nil {
		log.Fatal(err)
	}
}

func render(src, out string, quality int) error {
	f, err := os.Open(src)
	if err != nil {
		return err
	}
	defer f.Close()
	img, _, err := image.Decode(f)
	if err != nil {
		return fmt.Errorf("decode %s: %w", src, err)
	}
	if err := os.MkdirAll(out, 0o755); err != nil {
		return err
	}
	for _, size := range sizes {
		dst := image.NewRGBA(fit(img.Bounds(), size))
		draw.CatmullRom.Scale(dst, dst.Bounds(), img, img.Bounds(), draw.Over, nil)
		name := filepath.Join(out, fmt.Sprintf("%s-%d.jpg", filepath.Base(src), size))
		w, err := os.Create(name)
		if err != nil {
			return err
		}
		if err := jpeg.Encode(w, dst, &jpeg.Options{Quality: quality}); err != nil {
			w.Close()
			return err
		}
		w.Close()
	}
	return nil
}

func fit(b image.Rectangle, max int) image.Rectangle {
	w, h := b.Dx(), b.Dy()
	if w >= h {
		return image.Rect(0, 0, max, h*max/w)
	}
	return image.Rect(0, 0, w*max/h, max)
}
