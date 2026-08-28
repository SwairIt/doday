# Промпт для ChatGPT: обложка с моим интерфейсом

К промпту приложите архив `habr-cover-kit.zip` — там шесть скриншотов
интерфейса и уже готовые варианты обложки для примера.

## Что важно знать заранее

Модель **перерисовывает** интерфейс, а не вставляет ваш скриншот как есть.
Кириллица внутри перерисованного окна почти всегда получается «пьяной»:
буквы похожи на настоящие, но слов не складывают. Поэтому промпт ниже
построен так, чтобы интерфейс на обложке был **мелким и повёрнутым** —
тогда текст читается как фактура, а не как надпись, и глаз не спотыкается.

Если нужен идеально чёткий интерфейс — берите готовые файлы
`cover-ui-780x440.png` или `cover-780x440.png`: они собраны из настоящих
скриншотов, там всё честно и резко.

---

## Промпт (вставлять целиком, вместе с архивом)

```
I'm attaching screenshots of my own web product (a planner for students,
dark purple UI, Russian interface). I need a horizontal cover image for a
technical blog post, exactly 780×440 pixels.

Use the attached screenshots as the visual reference for the product UI:
keep my colour palette (deep indigo #0d0820 background, violet #7b2ff7
accents, soft cyan highlights), my card-based layout and my sidebar shape.

Composition:
- A single browser window shown at a slight three-quarter angle, floating in
  space, tilted about 12–15 degrees to the left, with a soft realistic drop
  shadow beneath it.
- Inside the window: my interface from the screenshots, rendered small and
  slightly out of focus toward the edges, so it reads as texture rather than
  as readable text. Do not invent new UI elements, buttons or icons that are
  not in the screenshots.
- Left third of the frame stays clean and empty — dark background with a soft
  violet glow. I will place my own headline there afterwards, so leave that
  area free of any objects.
- Background: deep indigo gradient with a large violet glow in the top right
  and a faint cyan glow in the bottom left, plus a very subtle square grid at
  low opacity.

Style: clean modern product-launch visual, the kind of hero image a SaaS
landing page would use. Flat, precise, no photorealistic desk scenes, no
hands, no people, no coffee cups, no plants, no 3D-rendered glossy plastic.

Absolutely no text anywhere in the image except the interface texture inside
the window — no headlines, no captions, no watermarks, no logos other than
the small purple square icon visible in my screenshots.

Output: 780×440 pixels, horizontal, sharp, ready to use as a cover image.
```

## Если хочется вариант «в устройствах»

Замените блок Composition на этот:

```
Composition: a laptop shown at a slight angle on the right side of the frame
and a phone standing in front of it slightly overlapping, both displaying my
interface from the attached screenshots — the laptop shows the desktop layout,
the phone shows the mobile one. Devices float without a desk or surface, on a
dark indigo background with a violet glow behind them. The left third of the
frame stays empty for my headline.
```

## Что попросить исправить, если результат не понравился

- «Make the interface smaller and less legible, it should read as texture» —
  если модель нарисовала кривые русские буквы крупно.
- «Remove everything from the left third, keep it empty» — если она
  заполнила место под заголовок.
- «Less glow, more contrast between the window and the background» — если
  вышло мутно.
- «Keep the exact purple from the screenshots, do not shift it to blue» —
  модели любят уводить фиолетовый в синий.
