import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  
  // Enable validation globally
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );
  
  // Enable CORS for development
  app.enableCors();
  
  const port = process.env.API_PORT || 3000;
  await app.listen(port);
  console.log(`API server running on http://localhost:${port}`);
}

bootstrap();
