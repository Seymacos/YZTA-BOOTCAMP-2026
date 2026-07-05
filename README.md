# **Takım İsmi**

Takım 65

# Ürün İle İlgili Bilgiler

## Takım Elemanları

- Şeyma Coştur: Product Owner, Developer
- Ayşegül Kılıç: Scrum Master, Developer
- Yağmur Dedekoç : Developer
- Fırat Karataşoğlu : Developer

## Ürün İsmi

SmartFinance — Kişisel Finans & Yatırım Asistanı

## Ürün Açıklaması

- SmartFinance, kullanıcıların harcamalarını takip etmesini, kategorilere ayırmasını ve kişisel bütçe önerileri almasını sağlayan yapay zeka destekli bir finansal asistan uygulamasıdır. Kullanıcı harcamalarını manuel olarak girebilir veya banka ekstresini yükleyebilir. Sistem makine öğrenmesi ile harcamaları otomatik kategorilere ayırır, anomali tespit eder ve canlı döviz, altın, hisse verilerini takip ederek kişisel öneriler üretir.


## Ürün Özellikleri

- Harcamaları otomatik kategorilere ayırma (TF-IDF + Random Forest)
- Türkçe ve İngilizce mağaza isimlerini tanıma
- Anomali tespiti (normalden sapan harcamaları bildirme)
- Canlı döviz, altın ve hisse takibi (yfinance)
- LLM agent ile kişisel bütçe ve yatırım önerileri
- Banka ekstresi PDF okuma


## Hedef Kitle

- Kişisel bütçesini takip etmek isteyen bireyler
- Yatırım kararlarını veriye dayandırmak isteyenler
- Aylık harcamalarını analiz etmek isteyen çalışanlar ve öğrenciler
- 18-65 yaş arası kullanıcılar

## Product Backlog URL

[Miro Backlog Board](https://miro.com/app/board/uXjVH_dU7Rw=/?share_link_id=760132369792)

---

# Sprint 1

- **Backlog düzeni ve Story seçimleri**: Backlog'umuz ilk yapılacak story'lere göre düzenlenmiştir. Sprint başına tahmin edilen puan sayısını geçmeyecek şekilde sıradan seçimler yapılmaktadır. Story başına çıkan tahmin puanı, toplam puanın yarısından az tutulmuştur. 

Story'ler yapılacak işlere (task'lere) bölünmüştür. Miro Board'da gözüken kırmızı item'lar yapılacak işleri (task) gösterirken, mavi item'lar story'leri temsil etmektedir.

- **Daily Scrum**: [DailyScrumMeetingSS_Sprint1.docx](https://github.com/user-attachments/files/29663753/DailyScrumMeetingSS_Sprint1.docx)


- **Sprint board update**: Sprint board screenshotları: 

<img width="445" height="469" alt="sprint1_started" src="https://github.com/user-attachments/assets/859828be-85b2-4b34-9612-630d47df5015" />

<img width="672" height="394" alt="sprint1_process1" src="https://github.com/user-attachments/assets/97d33678-f366-40cf-985e-e4425beafdee" />

<img width="680" height="379" alt="sprint1_process2" src="https://github.com/user-attachments/assets/ec14dfc8-4a77-4b58-8ec4-ea1e9c8fc93b" />

<img width="453" height="467" alt="sprint1_completed" src="https://github.com/user-attachments/assets/257f7fb6-ef3a-49c4-a449-536ecb6800c3" />

<img width="1635" height="930" alt="sprint1_burndown" src="https://github.com/user-attachments/assets/b7e072f9-de1f-4493-8834-9d87a1017337" />


- **Ürün Durumu**:
- Ürün Canlı link ## 🚀 Canlı Demo
[SmartFinance Dashboard](https://yzta-bootcamp-2026.onrender.com)
- Ekran görüntüleri:
<img width="949" height="556" alt="sprint1_ürünss1" src="https://github.com/user-attachments/assets/721fb487-101f-48a6-aa18-546ca097f463" />


<img width="953" height="457" alt="sprint1_ürünss2" src="https://github.com/user-attachments/assets/de0a7405-72f3-45fd-b1bd-241c769bd059" />


<img width="919" height="387" alt="sprint1_ürünss3" src="https://github.com/user-attachments/assets/6f741ba7-c5db-4ad6-b7e3-a5e8fddf7022" />


<img width="942" height="463" alt="sprint1_ürünss4" src="https://github.com/user-attachments/assets/0683e49d-3849-45d6-845b-0a9d736f11b6" />



- **Sprint Review**: 
Alınan kararlar:
  - Para birimi ayrıştırması iki farklı modülde farklı şekilde ele alındığı görülmüştür. Bu tutarsızlığın tek bir standarda bağlanması bir sonraki sprint'e aktarılmıştır.
  - Anomali tespiti özelliği, veri altyapısı hazır olmasına rağmen bu sprint kapsamına alınmamış, ilgili PBI Sprint 2'ye aktarılmıştır.
  - Çıkan ürünün çalışmasında ve testlerinde bir problem görülmemiştir; dashboard canlıya alınmış ve çalışan link sunulabilir durumdadır. Kategorilendirme modeli %99.66 doğrulukla test edilmiştir.
  - Ekstra koyulması gereken özellikler belirlenmiştir: kullanıcının kendi banka ekstresini yükleyebilmesi, anomali tespiti ve yatırımcı modu.
  - Sprint Review katılımcıları: Yağmur Dedekoç, Şeyma Coştur , Ayşegül Kılıç, Fırat Karataşoğlu

- **Sprint Retrospective:**
  - Mock veri ile paralel çalışma yaklaşımı başarılı olmuş, ekip üyeleri birbirini beklemeden ilerleyebilmiştir; bu yöntem sonraki sprintlerde de sürdürülecektir.
  - Para birimi (USD/INR) karışıklığı geç fark edilmiş, farklı modüllerde farklı çözümler üretilmiştir. Sonraki sprintte ortak kararların daha erken alınması ve modüller arası tutarlılığın planlama aşamasında netleştirilmesi gerektiği görülmüştür.
  - Tahmin puanları gözden geçirilmeli; bazı işlerin (özellikle veri temizleme ve entegrasyon) tahmin edilenden daha fazla efor gerektirdiği fark edilmiştir.
