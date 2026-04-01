
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib import colors
from PIL import Image, ImageDraw
def create_dummy_pdf(path):
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Course Title", styles['Title']))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Chapter 1: The Beginning", styles['Heading1']))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Introduction to Concepts", styles['Heading2']))
    story.append(Spacer(1, 12))

    text = "This is a <b>sample paragraph</b> for testing the extraction. " * 20
    story.append(Paragraph(text, styles['Normal']))
    story.append(Spacer(1, 12))

    img_path = "dummy_test_image.png"
    img = Image.new('RGB', (200, 100), color = 'red')
    d = ImageDraw.Draw(img)
    d.text((10,10), "Sample Text in Image", fill=(255,255,0))
    img.save(img_path)
    
    story.append(RLImage(img_path, width=200, height=100))
    story.append(Paragraph("Figure 1: value of red", styles['Normal']))
    story.append(Spacer(1, 12))
    # Table
    data = [['Col 1', 'Col 2', 'Col 3'],
            ['Val 1', 'Val 2', 'Val 3'],
            ['Val 4', 'Val 5', 'Val 6']]
    t = Table(data)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                           ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                           ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                           ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                           ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                           ('GRID', (0,0), (-1,-1), 1, colors.black)]))
    story.append(t)
    doc.build(story)

    if os.path.exists(img_path):
        os.remove(img_path)
    print(f"Created {path}")
if __name__ == "__main__":
    create_dummy_pdf("test_course.pdf")